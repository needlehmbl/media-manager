"""Server-side filesystem helpers: real download destinations.

The old destination field was effectively fake for anything outside
DOWNLOAD_DIR: /files only served DOWNLOAD_DIR and the web client guessed
URLs with a "downloads"-segment heuristic. This module is the fix:

- relative destinations resolve inside DOWNLOAD_DIR (unchanged default),
- absolute destinations may be anywhere under $HOME (or DOWNLOAD_DIR),
- a browse/mkdir API lets the UI pick or create those directories.
"""

from pathlib import Path

import app.config as config


def _download_dir() -> Path:
    return config.DOWNLOAD_DIR


def _home_dir() -> Path:
    return config.HOME_DIR


def allowed_roots() -> list[Path]:
    roots = [_download_dir(), _home_dir()]
    # Deduplicate (e.g. DOWNLOAD_DIR already under HOME).
    uniq: list[Path] = []
    for r in roots:
        if r not in uniq:
            uniq.append(r)
    return uniq


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def is_allowed(path: Path) -> bool:
    """True if path is inside one of the allowed roots."""
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()
    return any(resolved == r or _is_within(resolved, r) for r in allowed_roots())


def resolve_destination(destination: str | None) -> Path:
    """Map a user destination to a real directory, creating it.

    - empty -> DOWNLOAD_DIR (default, unchanged),
    - relative -> DOWNLOAD_DIR / destination,
    - absolute -> must live under $HOME or DOWNLOAD_DIR.

    Raises ValueError for disallowed absolute paths.
    """
    if not destination or not destination.strip():
        base = _download_dir()
    else:
        p = Path(destination.strip()).expanduser()
        if p.is_absolute():
            try:
                candidate = p.resolve()
            except OSError:
                candidate = p.absolute()
            if not is_allowed(candidate):
                raise ValueError(
                    f"Destination must be inside {_home_dir()} (got {destination.strip()})"
                )
            base = candidate
        else:
            base = _download_dir() / p
    base.mkdir(parents=True, exist_ok=True)
    return base


def browse(path: str | None) -> dict:
    """List subdirectories of path (defaults to HOME_DIR).

    Paths are clamped into the allowed roots: anything outside resolves to
    the nearest allowed root instead of erroring, so the picker can never
    escape the sandbox.
    """
    current = Path(path).expanduser() if path and path.strip() else _home_dir()
    try:
        current = current.resolve()
    except OSError:
        current = _home_dir()
    if not is_allowed(current) or not current.exists():
        current = _home_dir() if _home_dir().exists() else _download_dir()
    # If the user typed a file path, show its parent.
    if current.is_file():
        current = current.parent

    dirs: list[dict] = []
    try:
        for child in sorted(current.iterdir(), key=lambda p: p.name.lower()):
            if not child.is_dir() or child.is_symlink() and not child.exists():
                continue
            if child.name.startswith("."):
                continue
            dirs.append({"name": child.name, "path": str(child)})
    except OSError:
        pass

    parent = current.parent if is_allowed(current.parent) and current.parent != current else None
    return {
        "current": str(current),
        "parent": str(parent) if parent else None,
        "home": str(_home_dir()),
        "download_dir": str(_download_dir()),
        "dirs": dirs,
    }


def make_dir(path: str) -> Path:
    """Create a directory (and parents) inside the allowed roots."""
    if not path or not path.strip():
        raise ValueError("Provide a path")
    p = Path(path.strip()).expanduser()
    if not p.is_absolute():
        p = _home_dir() / p
    try:
        candidate = p.resolve()
    except OSError:
        candidate = p.absolute()
    if not is_allowed(candidate):
        raise ValueError(f"Destination must be inside {_home_dir()} (got {path.strip()})")
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate
