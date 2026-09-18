from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import require_api_key
from app.config import DOWNLOAD_DIR, MAX_CONCURRENT_JOBS, THUMBS_DIR
from app.db import engine, get_session, init_db
from app.jobs import enqueue, request_cancel, start_workers
from app.models import Channel, Job, JobStatus, LibraryItem


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await start_workers()
    try:
        from app.scheduler import start_scheduler

        start_scheduler()
    except Exception:
        pass
    yield


app = FastAPI(title="Media Manager API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- Jobs ----------


class JobCreate(BaseModel):
    url: str | None = None
    urls: list[str] | None = None
    source: str = "yt-dlp"
    destination: str | None = None


@app.post("/jobs", dependencies=[Depends(require_api_key)])
async def create_job(payload: JobCreate, session: Session = Depends(get_session)):
    urls = []
    if payload.urls:
        urls.extend([u.strip() for u in payload.urls if u.strip()])
    if payload.url and payload.url.strip():
        urls.append(payload.url.strip())
    if not urls:
        raise HTTPException(400, "Provide url or urls")
    created_ids = []
    for u in urls:
        job = Job(url=u, source=payload.source or "yt-dlp", destination=payload.destination)
        session.add(job)
        session.commit()
        session.refresh(job)
        created_ids.append(job.id)
        await enqueue(job.id)
    created = session.exec(select(Job).where(Job.id.in_(created_ids))).all()
    return created if len(created) > 1 else created[0]


@app.get("/jobs", dependencies=[Depends(require_api_key)])
def list_jobs(status: str | None = None, session: Session = Depends(get_session)):
    q = select(Job).order_by(Job.created_at.desc())
    if status:
        q = q.where(Job.status == status)
    return session.exec(q).all()


@app.get("/jobs/{job_id}", dependencies=[Depends(require_api_key)])
def get_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.post("/jobs/{job_id}/retry", dependencies=[Depends(require_api_key)])
async def retry_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    job.status = JobStatus.QUEUED
    job.progress = 0.0
    job.error = None
    job.updated_at = datetime.utcnow()
    session.add(job)
    session.commit()
    await enqueue(job.id)
    return job


@app.post("/jobs/{job_id}/cancel", dependencies=[Depends(require_api_key)])
def cancel_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    ok = request_cancel(job_id)
    if not ok:
        raise HTTPException(409, "Job is not cancellable (already done/failed)")
    return {"id": job_id, "cancelled": True}


@app.delete("/jobs/{job_id}", dependencies=[Depends(require_api_key)])
def delete_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    request_cancel(job_id)
    session.delete(job)
    session.commit()
    return {"deleted": job_id}


# ---------- Library ----------


@app.get("/library", dependencies=[Depends(require_api_key)])
def list_library(
    q: str | None = None,
    source: str | None = None,
    tag: str | None = None,
    session: Session = Depends(get_session),
):
    query = select(LibraryItem).order_by(LibraryItem.downloaded_at.desc())
    if source:
        query = query.where(LibraryItem.source == source)
    items = session.exec(query).all()
    if q:
        ql = q.lower()
        items = [i for i in items if ql in i.title.lower() or ql in (i.file_path or "").lower()]
    if tag:
        tl = tag.lower()
        items = [i for i in items if tl in (i.tags or "").lower()]
    return items


@app.get("/library/{item_id}", dependencies=[Depends(require_api_key)])
def get_library_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(LibraryItem, item_id)
    if not item:
        raise HTTPException(404, "Not found")
    return item


@app.delete("/library/{item_id}", dependencies=[Depends(require_api_key)])
def delete_library_item(item_id: int, delete_file: bool = False, session: Session = Depends(get_session)):
    item = session.get(LibraryItem, item_id)
    if not item:
        raise HTTPException(404, "Not found")
    if delete_file:
        try:
            Path(item.file_path).unlink(missing_ok=True)
        except Exception:
            pass
    session.delete(item)
    session.commit()
    return {"deleted": item_id}


# ---------- Channels ----------


class ChannelCreate(BaseModel):
    url: str
    check_interval: int = 3600
    active: bool = True


class ChannelUpdate(BaseModel):
    url: str | None = None
    check_interval: int | None = None
    active: bool | None = None


@app.post("/channels", dependencies=[Depends(require_api_key)])
def create_channel(payload: ChannelCreate, session: Session = Depends(get_session)):
    ch = Channel(url=payload.url, check_interval=payload.check_interval, active=payload.active)
    session.add(ch)
    session.commit()
    session.refresh(ch)
    try:
        from app.scheduler import sync_channel_jobs

        sync_channel_jobs()
    except Exception:
        pass
    return ch


@app.get("/channels", dependencies=[Depends(require_api_key)])
def list_channels(session: Session = Depends(get_session)):
    return session.exec(select(Channel)).all()


@app.get("/channels/{cid}", dependencies=[Depends(require_api_key)])
def get_channel(cid: int, session: Session = Depends(get_session)):
    ch = session.get(Channel, cid)
    if not ch:
        raise HTTPException(404, "Not found")
    return ch


@app.patch("/channels/{cid}", dependencies=[Depends(require_api_key)])
def update_channel(cid: int, payload: ChannelUpdate, session: Session = Depends(get_session)):
    ch = session.get(Channel, cid)
    if not ch:
        raise HTTPException(404, "Not found")
    if payload.url is not None:
        ch.url = payload.url
    if payload.check_interval is not None:
        ch.check_interval = max(300, payload.check_interval)
    if payload.active is not None:
        ch.active = payload.active
    session.add(ch)
    session.commit()
    session.refresh(ch)
    try:
        from app.scheduler import sync_channel_jobs

        sync_channel_jobs()
    except Exception:
        pass
    return ch


@app.delete("/channels/{cid}", dependencies=[Depends(require_api_key)])
def delete_channel(cid: int, session: Session = Depends(get_session)):
    ch = session.get(Channel, cid)
    if not ch:
        raise HTTPException(404, "Not found")
    session.delete(ch)
    session.commit()
    try:
        from app.scheduler import sync_channel_jobs

        sync_channel_jobs()
    except Exception:
        pass
    return {"deleted": cid}


@app.post("/channels/{cid}/check", dependencies=[Depends(require_api_key)])
async def trigger_check(cid: int, session: Session = Depends(get_session)):
    ch = session.get(Channel, cid)
    if not ch:
        raise HTTPException(404, "Not found")
    from app.scheduler import check_channel

    await check_channel(cid)
    return {"checked": cid}


# ---------- Settings ----------


@app.get("/settings", dependencies=[Depends(require_api_key)])
def get_settings():
    return {
        "download_dir": str(DOWNLOAD_DIR),
        "max_concurrent_jobs": MAX_CONCURRENT_JOBS,
        "auth_enabled": bool(__import__("app.config", fromlist=["API_KEY"]).API_KEY),
    }


@app.get("/settings/default-destination", dependencies=[Depends(require_api_key)])
def default_destination():
    return {"destination": str(DOWNLOAD_DIR)}


# Serve downloaded files + thumbnails for in-browser playback (auth via query not enforced; LAN tool)
try:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass
app.mount("/files", StaticFiles(directory=str(DOWNLOAD_DIR), html=False, check_dir=False), name="files")
app.mount("/thumbs", StaticFiles(directory=str(THUMBS_DIR), html=False, check_dir=False), name="thumbs")
