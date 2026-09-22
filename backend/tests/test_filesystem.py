import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test-media-manager.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402


def _client():
    init_db()
    return TestClient(app)


def test_browse_defaults_to_home(tmp_path, monkeypatch):
    import app.config as cfg
    from app.filesystem import browse

    monkeypatch.setattr(cfg, "HOME_DIR", tmp_path)
    (tmp_path / "Music").mkdir()
    (tmp_path / ".hidden").mkdir()
    res = browse(None)
    assert res["current"] == str(tmp_path)
    names = [d["name"] for d in res["dirs"]]
    assert "Music" in names
    assert ".hidden" not in names


def test_browse_clamps_outside_to_home(tmp_path, monkeypatch):
    import app.config as cfg
    from app.filesystem import browse

    monkeypatch.setattr(cfg, "HOME_DIR", tmp_path)
    monkeypatch.setattr(cfg, "DOWNLOAD_DIR", tmp_path / "dl")
    res = browse("/etc")
    assert res["current"] == str(tmp_path)


def test_mkdir_creates_nested_and_rejects_outside(tmp_path, monkeypatch):
    import pytest

    import app.config as cfg
    from app.filesystem import make_dir

    monkeypatch.setattr(cfg, "HOME_DIR", tmp_path)
    monkeypatch.setattr(cfg, "DOWNLOAD_DIR", tmp_path / "dl")
    created = make_dir(str(tmp_path / "Videos" / "2026"))
    assert created.is_dir()
    with pytest.raises(ValueError):
        make_dir("/etc/media-manager-evil")


def test_fs_endpoints(tmp_path, monkeypatch):
    import app.config as cfg

    monkeypatch.setattr(cfg, "HOME_DIR", tmp_path)
    (tmp_path / "Music").mkdir(exist_ok=True)
    client = _client()

    r = client.get("/fs/roots")
    assert r.status_code == 200
    assert r.json()["home"] == str(tmp_path)

    r = client.get("/fs/browse", params={"path": str(tmp_path)})
    assert r.status_code == 200
    assert any(d["name"] == "Music" for d in r.json()["dirs"])

    r = client.post("/fs/mkdir", json={"path": str(tmp_path / "New Folder")})
    assert r.status_code == 200, r.text
    assert (tmp_path / "New Folder").is_dir()

    r = client.post("/fs/mkdir", json={"path": "/etc/nope-mm"})
    assert r.status_code == 400


def test_reject_outside_destination_on_job_create(monkeypatch):
    import app.jobs as jobs_mod
    import app.main as main_mod

    async def fake_enqueue(job_id: int):
        return None

    monkeypatch.setattr(jobs_mod, "enqueue", fake_enqueue)
    monkeypatch.setattr(main_mod, "enqueue", fake_enqueue)

    client = _client()
    r = client.post("/jobs", json={"urls": ["https://example.com/v1"], "destination": "/etc/nope-mm"})
    assert r.status_code == 400


def test_library_file_serves_any_destination(tmp_path):
    from sqlmodel import Session

    from app.db import engine
    from app.models import LibraryItem

    media = tmp_path / "song.flac"
    media.write_bytes(b"fake-flac-bytes")
    with Session(engine) as s:
        item = LibraryItem(title="Outside Song", file_path=str(media), source="yt-dlp")
        s.add(item)
        s.commit()
        s.refresh(item)
        item_id = item.id
    try:
        client = _client()
        r = client.get(f"/library/{item_id}/file")
        assert r.status_code == 200
        assert r.content == b"fake-flac-bytes"
    finally:
        with Session(engine) as s:
            obj = s.get(LibraryItem, item_id)
            if obj:
                s.delete(obj)
                s.commit()
