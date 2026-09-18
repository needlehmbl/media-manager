import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test-media-manager.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402


def _client():
    init_db()
    return TestClient(app)


def test_health():
    client = _client()
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_settings():
    client = _client()
    r = client.get("/settings")
    assert r.status_code == 200
    body = r.json()
    assert "download_dir" in body
    assert "max_concurrent_jobs" in body


def test_jobs_crud(monkeypatch):
    import app.jobs as jobs_mod
    import app.main as main_mod

    async def fake_enqueue(job_id: int):
        return None

    monkeypatch.setattr(jobs_mod, "enqueue", fake_enqueue)
    monkeypatch.setattr(main_mod, "enqueue", fake_enqueue)

    client = _client()
    # bulk create: single + playlist-style multi URL
    r = client.post(
        "/jobs",
        json={"urls": ["https://example.com/v1", "https://example.com/v2"], "destination": "test-dir"},
    )
    assert r.status_code == 200, r.text
    jobs = r.json()
    assert isinstance(jobs, list) and len(jobs) == 2
    jid = jobs[0]["id"]

    r = client.get("/jobs")
    assert r.status_code == 200
    assert len(r.json()) >= 2

    r = client.get(f"/jobs/{jid}")
    assert r.status_code == 200

    r = client.post(f"/jobs/{jid}/retry")
    assert r.status_code == 200

    r = client.post(f"/jobs/{jid}/cancel")
    assert r.status_code in (200, 409)

    r = client.delete(f"/jobs/{jid}")
    assert r.status_code == 200


def test_library_search():
    from sqlmodel import Session

    from app.db import engine
    from app.models import LibraryItem

    with Session(engine) as s:
        s.add(
            LibraryItem(title="Test Video One", file_path="/data/downloads/test.mp4", source="yt-dlp", tags="music")
        )
        s.commit()
    client = _client()
    r = client.get("/library?q=test+video")
    assert r.status_code == 200
    assert any("Test Video One" in i["title"] for i in r.json())
    r = client.get("/library?source=yt-dlp")
    assert r.status_code == 200


def test_channels_crud(monkeypatch):
    import app.scheduler as sched

    monkeypatch.setattr(sched, "sync_channel_jobs", lambda: None)
    client = _client()
    r = client.post("/channels", json={"url": "https://example.com/channel", "check_interval": 900})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert r.json()["active"] is True

    r = client.patch(f"/channels/{cid}", json={"active": False})
    assert r.status_code == 200
    assert r.json()["active"] is False

    r = client.get("/channels")
    assert r.status_code == 200

    r = client.delete(f"/channels/{cid}")
    assert r.status_code == 200
