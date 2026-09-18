import os
from pathlib import Path

DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./data/downloads"))
try:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))
API_KEY = os.getenv("API_KEY", "")

YTDLP_BIN = os.getenv("YTDLP_BIN", "yt-dlp")
YTDLP_COOKIES_FROM_BROWSER = os.getenv("YTDLP_COOKIES_FROM_BROWSER", "")
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")

THUMBS_DIR = DOWNLOAD_DIR / ".thumbs"
try:
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
