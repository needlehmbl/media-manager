from pathlib import Path

from app.scrapers.ytdlp_runner import build_command, resolve_base


def test_resolve_base_defaults(tmp_path, monkeypatch):
    import app.config as cfg

    monkeypatch.setattr(cfg, "DOWNLOAD_DIR", tmp_path)
    base = resolve_base(None)
    assert base == tmp_path


def test_resolve_base_relative_contained(tmp_path, monkeypatch):
    import app.config as cfg

    monkeypatch.setattr(cfg, "DOWNLOAD_DIR", tmp_path)
    base = resolve_base("my-videos")
    assert str(base).startswith(str(tmp_path))


def test_resolve_base_absolute_home_allowed(tmp_path, monkeypatch):
    import app.config as cfg

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(cfg, "HOME_DIR", fake_home)
    monkeypatch.setattr(cfg, "DOWNLOAD_DIR", tmp_path / "dl")
    target = fake_home / "Music" / "rips"
    base = resolve_base(str(target))
    assert base == target
    assert target.is_dir()


def test_resolve_base_absolute_outside_rejected(tmp_path, monkeypatch):
    import app.config as cfg

    import pytest

    monkeypatch.setattr(cfg, "HOME_DIR", tmp_path / "home")
    monkeypatch.setattr(cfg, "DOWNLOAD_DIR", tmp_path / "dl")
    with pytest.raises(ValueError):
        resolve_base("/etc/media-manager-evil")


def test_build_command_playlist_folder(tmp_path):
    cmd = build_command("https://example.com/playlist", tmp_path, True, "My Playlist")
    o_idx = cmd.index("-o") + 1
    assert "My Playlist" in cmd[o_idx]
    assert "--yes-playlist" in cmd
    assert "--continue" in cmd
    assert "--embed-metadata" in cmd
    assert "--ignore-errors" in cmd


def test_build_command_single(tmp_path):
    cmd = build_command("https://example.com/v", tmp_path, False, None)
    o_idx = cmd.index("-o") + 1
    assert "%(title)s" in cmd[o_idx]
    assert "--concurrent-fragments" in cmd


def test_build_command_ffmpeg_location_is_absolute(tmp_path, monkeypatch):
    import app.scrapers.ytdlp_runner as r

    monkeypatch.setattr(r.shutil, "which", lambda _: "/usr/bin/ffmpeg")
    cmd = build_command("https://example.com/v", tmp_path, False, None)
    loc = cmd[cmd.index("--ffmpeg-location") + 1]
    assert loc == "/usr/bin/ffmpeg"
