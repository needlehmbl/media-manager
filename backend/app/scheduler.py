"""Recurring channel checks via APScheduler."""

import asyncio
import json
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session, select

from app.config import YTDLP_BIN, YTDLP_COOKIES_FROM_BROWSER
from app.db import engine
from app.models import Channel, Job, JobStatus, LibraryItem

scheduler = AsyncIOScheduler()


async def _flat_urls(channel_url: str) -> list[tuple[str, str]]:
    cmd = [YTDLP_BIN, "--flat-playlist", "-J", "--no-warnings", channel_url]
    if YTDLP_COOKIES_FROM_BROWSER:
        cmd[1:1] = ["--cookies-from-browser", YTDLP_COOKIES_FROM_BROWSER]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode != 0:
            return []
        data = json.loads(out.decode("utf-8", "replace"))
        items = []
        for e in data.get("entries") or []:
            vid = e.get("id")
            if not vid:
                continue
            # Reconstruct watch URL; extractor-agnostic fallback to raw URL field.
            url = e.get("url") or e.get("webpage_url") or ""
            if url and not url.startswith("http"):
                url = f"https://www.youtube.com/watch?v={vid}"
            items.append((url, e.get("title") or vid))
        return items
    except Exception:
        return []


async def check_channel(channel_id: int):
    from app.jobs import enqueue

    with Session(engine) as s:
        ch = s.get(Channel, channel_id)
        if not ch or not ch.active:
            return
        known_urls = {j.url for j in s.exec(select(Job)).all()}
        known_titles = {li.title for li in s.exec(select(LibraryItem)).all()}

    entries = await _flat_urls(ch.url)
    new = 0
    for url, title in entries:
        if not url or url in known_urls or title in known_titles:
            continue
        with Session(engine) as s:
            job = Job(url=url, source="yt-dlp", status=JobStatus.QUEUED)
            s.add(job)
            s.commit()
            s.refresh(job)
            jid = job.id
        await enqueue(jid)
        new += 1

    with Session(engine) as s:
        ch = s.get(Channel, channel_id)
        if ch:
            ch.last_checked = datetime.utcnow()
            s.add(ch)
            s.commit()


def sync_channel_jobs():
    with Session(engine) as s:
        channels = s.exec(select(Channel).where(Channel.active == True)).all()  # noqa: E712
        for ch in channels:
            scheduler.add_job(
                check_channel,
                "interval",
                seconds=max(300, ch.check_interval),
                args=[ch.id],
                id=f"channel-{ch.id}",
                replace_existing=True,
            )


def start_scheduler():
    if not scheduler.running:
        scheduler.start()
    sync_channel_jobs()
