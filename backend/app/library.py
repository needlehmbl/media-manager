import asyncio
import shutil
import subprocess
from pathlib import Path

from sqlmodel import Session

from app.config import FFMPEG_BIN, THUMBS_DIR
from app.models import LibraryItem

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v"}


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
        thumb = _grab_thumbnail(f) if f.suffix.lower() in VIDEO_EXTS else None
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
