"""yt-dlp subprocess wrapper: playlists, metadata, resume, progress.

Deliberately drops the old turbo.cr special-case — generic yt-dlp handles
most video sites.
"""

import asyncio
import json
import logging
import re
import shutil
from collections import deque
from pathlib import Path

from app.config import (
    DOWNLOAD_DIR,
    FFMPEG_BIN,
    YTDLP_BIN,
    YTDLP_COOKIES_FROM_BROWSER,
)

PROGRESS_RE = re.compile(r"\[download\]\s+(?P<pct>\d+(?:\.\d+)?)%")
DEST_RE = re.compile(r"\[download\] Destination:\s(?P<path>.+)")
MERGE_RE = re.compile(r"\[Merger\] Merging formats into \"(?P<path>.+)\"")

logger = logging.getLogger(__name__)
TAIL_LINES = 30


def resolve_base(destination: str | None) -> Path:
    if destination and destination.strip():
        p = Path(destination.strip()).expanduser()
        # Contain relative paths inside DOWNLOAD_DIR; allow absolute paths.
        base = p if p.is_absolute() else (DOWNLOAD_DIR / p)
    else:
        base = DOWNLOAD_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base


async def probe_entries(url: str) -> tuple[bool, str | None, int]:
    """Return (is_playlist, playlist_title, entry_count) via flat JSON dump."""
    cmd = [YTDLP_BIN, "--flat-playlist", "-J", "--no-warnings", url]
    if YTDLP_COOKIES_FROM_BROWSER:
        cmd[1:1] = ["--cookies-from-browser", YTDLP_COOKIES_FROM_BROWSER]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode != 0:
            return False, None, 0
        data = json.loads(out.decode("utf-8", "replace"))
        entries = data.get("entries") or []
        if data.get("_type") == "playlist" or len(entries) > 1:
            title = data.get("title") or "playlist"
            return True, re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip() or "playlist", len(entries)
        return False, None, 0
    except Exception:
        return False, None, 0


def build_command(url: str, base: Path, is_playlist: bool, playlist_title: str | None) -> list[str]:
    if is_playlist and playlist_title:
        # Playlist -> dedicated folder named after the playlist.
        out_tmpl = str(base / playlist_title / "%(playlist_index)03d - %(title)s.%(ext)s")
    else:
        out_tmpl = str(base / "%(uploader)s" / "%(title)s.%(ext)s")

    cmd = [
        YTDLP_BIN,
        "--newline",  # one progress line at a time for parsing
        "--progress",
        "--yes-playlist",  # recursive playlist download
        "--continue",  # resume interrupted downloads
        "--retries", "10",
        "--fragment-retries", "10",
        "--concurrent-fragments", "4",
        # A postprocessor hiccup (thumbnail/subs/chapters) must not fail the
        # job when the media itself downloaded fine — we verify output files
        # ourselves below. ("--ignore-errors" = postprocessing errors still
        # count the download as successful.)
        "--ignore-errors",
        "--no-mtime",
        "--embed-metadata",
        "--embed-thumbnail",
        "--embed-chapters",
        "--embed-subs",
        "--sub-langs", "en.*",
        "--restrict-filenames",
        "-o", out_tmpl,
    ]
    ffmpeg_path = shutil.which(FFMPEG_BIN)
    if ffmpeg_path:
        # Must be the resolved absolute path: yt-dlp treats a bare name as a
        # relative path and then reports "ffmpeg not found", which breaks
        # merging and every embed postprocessor (exit code 1 at 100%).
        cmd += ["--ffmpeg-location", ffmpeg_path]
    if YTDLP_COOKIES_FROM_BROWSER:
        cmd += ["--cookies-from-browser", YTDLP_COOKIES_FROM_BROWSER]
    cmd.append(url)
    return cmd


async def run_download(
    url: str,
    destination: str | None,
    progress_cb=None,
    cancel_event: asyncio.Event | None = None,
) -> list[Path]:
    """Run yt-dlp, report progress 0-100 via callback, return downloaded files."""
    base = resolve_base(destination)
    before = {p for p in base.rglob("*") if p.is_file()}

    is_playlist, playlist_title, _ = await probe_entries(url)
    cmd = build_command(url, base, is_playlist, playlist_title)

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    outputs: list[Path] = []
    tail: deque[str] = deque(maxlen=TAIL_LINES)

    async def _watch_cancel():
        if cancel_event is None:
            return
        await cancel_event.wait()
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass

    watcher = asyncio.create_task(_watch_cancel()) if cancel_event else None
    try:
        assert proc.stdout is not None
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", "replace").strip()
            tail.append(text)
            m = PROGRESS_RE.search(text)
            if m and progress_cb:
                try:
                    await progress_cb(min(100.0, max(0.0, float(m.group("pct")))))
                except Exception:
                    pass
            for rx in (DEST_RE, MERGE_RE):
                dm = rx.search(text)
                if dm:
                    outputs.append(Path(dm.group("path").strip()))
        await proc.wait()
    finally:
        if watcher:
            watcher.cancel()

    if cancel_event and cancel_event.is_set():
        raise asyncio.CancelledError()

    tail_text = "\n".join(tail)[-2000:]

    if proc.returncode != 0:
        # yt-dlp only reaches this on hard failures now (--ignore-errors
        # absorbs postprocessing hiccups). Include its own last words so the
        # Job error actually says what happened.
        logger.warning("yt-dlp exited %s for %s:\n%s", proc.returncode, url, tail_text)
        raise RuntimeError(f"yt-dlp exited with code {proc.returncode} for {url}:\n{tail_text}")

    if progress_cb:
        try:
            await progress_cb(100.0)
        except Exception:
            pass

    # Fallback: anything new under base counts as output (covers playlists).
    after = {p for p in base.rglob("*") if p.is_file()}
    new_files = sorted(after - before)
    # Prefer explicitly captured paths, else discovered ones.
    existing = [p for p in outputs if p.exists()]
    found = existing or [p for p in new_files if p.suffix.lower() not in {".part", ".tmp", ".ytdl"}]
    if not found:
        # Everything was skipped/failed (e.g. unavailable video): don't
        # report success with no files.
        logger.warning("yt-dlp produced no files for %s:\n%s", url, tail_text)
        raise RuntimeError(f"yt-dlp finished without producing any files for {url}:\n{tail_text}")
    return found
