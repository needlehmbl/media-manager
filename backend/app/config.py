import os
from pathlib import Path

DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./data/downloads"))
try:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
# Absolute, resolved form used for path comparisons and /files serving.
try:
    DOWNLOAD_DIR = DOWNLOAD_DIR.resolve()
except OSError:
    pass

# Destinations may live anywhere under the server user's home directory (or
# under DOWNLOAD_DIR, which in Docker is /data). Browsing is sandboxed to
# these roots.
HOME_DIR = Path.home()
try:
    HOME_DIR = HOME_DIR.resolve()
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
