"""Parallel job queue: asyncio workers running yt-dlp subprocesses."""

import asyncio
from datetime import datetime

from sqlmodel import Session, select

from app.config import MAX_CONCURRENT_JOBS
from app.db import engine
from app.library import index_files
from app.models import Job, JobStatus
from app.scrapers.playwright_runner import run_doodstream
from app.scrapers.ytdlp_runner import run_download

_queue: asyncio.Queue[int] = asyncio.Queue()
_workers: list[asyncio.Task] = []
_cancel_events: dict[int, asyncio.Event] = {}
_started = False
_lock = asyncio.Lock()


def _update(job_id: int, **fields):
    with Session(engine) as s:
        job = s.get(Job, job_id)
        if not job:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        job.updated_at = datetime.utcnow()
        s.add(job)
        s.commit()


async def _progress_cb(job_id: int, pct: float):
    await asyncio.to_thread(_update, job_id, progress=pct)


async def _run_one(job_id: int):
    with Session(engine) as s:
        job = s.get(Job, job_id)
        if not job or job.status == JobStatus.CANCELLED:
            return
        url, source, dest = job.url, job.source, job.destination
        audio_only = bool(getattr(job, "audio_only", False))
    cancel = asyncio.Event()
    _cancel_events[job_id] = cancel
    _update(job_id, status=JobStatus.RUNNING, error=None, progress=0.0)

    async def cb(pct: float):
        await _progress_cb(job_id, pct)

    try:
        runner = run_doodstream if source == "doodstream" else run_download
        files = await runner(url, dest, cb, cancel, audio_only)
        out = str(files[0].parent if len(files) > 1 else files[0]) if files else None
        _update(job_id, status=JobStatus.DONE, progress=100.0, output_path=out)
        with Session(engine) as s2:
            job2 = s2.get(Job, job_id)
            title = (files[0].stem if files else job2.url)[:200]
            s2.add(job2)
            s2.commit()
            index_files(s2, files, source=job2.source)
            _update(job_id, title=title)
    except asyncio.CancelledError:
        _update(job_id, status=JobStatus.CANCELLED, error="cancelled")
    except Exception as e:
        _update(job_id, status=JobStatus.FAILED, error=str(e)[:2000])
    finally:
        _cancel_events.pop(job_id, None)


async def _worker():
    while True:
        job_id = await _queue.get()
        try:
            await _run_one(job_id)
        finally:
            _queue.task_done()


async def start_workers(count: int = MAX_CONCURRENT_JOBS):
    global _started
    async with _lock:
        if _started:
            # scale up if requested higher
            while len(_workers) < count:
                _workers.append(asyncio.create_task(_worker()))
            return
        _started = True
        for _ in range(max(1, count)):
            _workers.append(asyncio.create_task(_worker()))
        # requeue jobs left queued/running from a previous run (crash recovery)
        with Session(engine) as s:
            stale = s.exec(
                select(Job).where(Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))
            ).all()
            for j in stale:
                _update(j.id, status=JobStatus.QUEUED, progress=0.0)
                _queue.put_nowait(j.id)


async def enqueue(job_id: int):
    await start_workers()
    await _queue.put(job_id)


def request_cancel(job_id: int) -> bool:
    ev = _cancel_events.get(job_id)
    if ev:
        ev.set()
        return True
    # not running yet: mark cancelled so worker skips it
    with Session(engine) as s:
        job = s.get(Job, job_id)
        if job and job.status == JobStatus.QUEUED:
            job.status = JobStatus.CANCELLED
            s.add(job)
            s.commit()
            return True
    return False
