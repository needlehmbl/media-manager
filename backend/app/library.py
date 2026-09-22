import asyncio
import shutil
import subprocess
from pathlib import Path

from sqlmodel import Session

from app.config import FFMPEG_BIN, THUMBS_DIR
from app.models import LibraryItem

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v"}
AUDIO_EXTS = {".flac", ".mp3", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wav", ".wma", ".alac", ".aiff"}
# Sidecar/non-media files yt-dlp may leave behind — never index these.
SKIP_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".vtt", ".srt", ".sub", ".part", ".tmp", ".ytdl"}
SKIP_COMPOUND = {".info.json", ".description"}


def _grab_audio_cover(audio: Path) -> Path | None:
    """Extract embedded cover art from an audio file via ffmpeg."""
    if not shutil.which(FFMPEG_BIN):
        return None
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    thumb = THUMBS_DIR / (audio.stem[:120] + ".jpg")
    if thumb.exists():
        return thumb
    try:
        subprocess.run(
            [FFMPEG_BIN, "-y", "-i", str(audio), "-an", "-vcodec", "copy", str(thumb)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
        return thumb if thumb.exists() and thumb.stat().st_size > 0 else None
    except Exception:
        return None


def _grab_thumbnail(video: Path) -> Path | None:
    if not shutil.which(FFMPEG_BIN):
        return None
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    thumb = THUMBS_DIR / (video.stem[:120] + ".jpg")
    if thumb.exists():
        return thumb
    try:
        subprocess.run(
            [FFMPEG_BIN, "-y", "-ss", "1", "-i", str(video), "-vframes", "1", "-q:v", "4", str(thumb)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
        return thumb if thumb.exists() else None
    except Exception:
        return None


def index_files(session: Session, files: list[Path], source: str, tags: str | None = None) -> list[LibraryItem]:
    items: list[LibraryItem] = []
    for f in files:
        if not f.exists() or not f.is_file():
            continue
        sfx = f.suffix.lower()
        if sfx in SKIP_EXTS or "".join(f.suffixes[-2:]).lower() in SKIP_COMPOUND:
            continue
        thumb: Path | None = None
        if sfx in VIDEO_EXTS:
            thumb = _grab_thumbnail(f)
        elif sfx in AUDIO_EXTS:
            thumb = _grab_audio_cover(f)
        item = LibraryItem(
            title=f.stem.replace("_", " "),
            file_path=str(f),
            thumbnail_path=str(thumb) if thumb else None,
            source=source,
            tags=tags,
        )
        session.add(item)
        items.append(item)
    session.commit()
    for it in items:
        session.refresh(it)
    return items


async def index_files_async(*args, **kwargs):
    return await asyncio.to_thread(index_files, *args, **kwargs)
