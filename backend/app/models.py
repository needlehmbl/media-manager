from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobSource(str, Enum):
    YTDLP = "yt-dlp"
    DOODSTREAM = "doodstream"


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str
    source: str = Field(default=JobSource.YTDLP)
    status: str = Field(default=JobStatus.QUEUED)
    progress: float = Field(default=0.0)
    output_path: Optional[str] = None
    destination: Optional[str] = Field(default=None, description="user-chosen base dir; defaults to DOWNLOAD_DIR")
    audio_only: bool = Field(default=False, description="audio-only FLAC download")
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None


class Channel(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str
    check_interval: int = Field(default=3600, description="seconds between checks")
    last_checked: Optional[datetime] = None
    active: bool = Field(default=True)


class LibraryItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    file_path: str
    thumbnail_path: Optional[str] = None
    source: str = Field(default=JobSource.YTDLP)
    downloaded_at: datetime = Field(default_factory=datetime.utcnow)
    tags: Optional[str] = Field(default=None, description="comma-separated tags")
