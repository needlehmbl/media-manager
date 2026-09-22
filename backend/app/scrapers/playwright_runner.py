"""DoodStream source: routes through yt-dlp (generic extractor).

No legacy Playwright scraper was found in the workspace, and per user request
turbo.cr handling was dropped. If a dedicated Playwright flow is needed later,
implement `run_doodstream()` here (intercept /pass_md5/ -> signed URL -> yt-dlp/curl)
and keep this yt-dlp fallback.
"""

import asyncio
from pathlib import Path

from app.scrapers.ytdlp_runner import run_download


async def run_doodstream(
    url: str,
    destination: str | None,
    progress_cb=None,
    cancel_event: asyncio.Event | None = None,
    audio_only: bool = False,
) -> list[Path]:
    return await run_download(url, destination, progress_cb, cancel_event, audio_only)
