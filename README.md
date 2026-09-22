# Media Manager

Self-hosted web app for downloading, tracking, and browsing online videos.
Paste URLs (singles or playlists) from most video sites, watch parallel
workers download them with metadata embedded, then search and play everything
from a dark-themed library. Optional recurring channel checks auto-queue new
uploads, and an API key locks the API for self-hosting.

## Features

- **Parallel download queue** — paste multiple URLs (one per line); workers run
  up to `MAX_CONCURRENT_JOBS` downloads at once with live progress, retry
  (resumes interrupted files via `yt-dlp --continue`), cancel, and delete.
- **Playlist recursion** — playlist/channel URLs are probed up front and
  downloaded recursively into `<destination>/<Playlist Title>/` with indexed
  filenames (`001 - Title.ext`).
- **Per-job destinations** — pick any folder under your home directory (or a
  subfolder of the default) via the 📂 Browse picker, which can also create
  new folders; empty means the default `DOWNLOAD_DIR`. Library playback
  streams by item id so files outside the default still play.
- **Metadata baked in** — `--embed-metadata --embed-thumbnail --embed-chapters
  --embed-subs` on every download; filenames restricted to safe ASCII.
- **Library** — completed downloads are auto-indexed with ffmpeg-grabbed
  thumbnails, full-text search, source/tag filters, in-browser playback served
  from `/files`, and delete-record vs delete-record+file.
- **Channels** — register channel/playlist URLs with a check interval;
  APScheduler periodically diffs flat-playlist entries against known jobs and
  auto-enqueues anything new.
- **Auth** — single `API_KEY` env var checked as `X-API-Key` on all routes
  (open access when unset; the web UI stores the key in localStorage).
- **Sources** — generic `yt-dlp` extractor (most sites) plus a `doodstream`
  source label routed through the same runner (dedicated Playwright
  `/pass_md5/` flow can be plugged into `playwright_runner.py` later).

## Tech stack

| Layer    | Tech |
|----------|------|
| Backend  | Python 3.12, FastAPI, SQLModel + SQLite, APScheduler, yt-dlp, ffmpeg |
| Frontend | React 19, Vite 6, TypeScript, Tailwind CSS 3, React Router 7 |
| Infra    | Docker Compose (api + web, hot-reload volumes, `/data` volume) |

## Prerequisites

- Python 3.12+, Node.js 24+, plus `yt-dlp` and `ffmpeg` on `PATH` (the
  backend shells out to both for downloads and thumbnails).
- Docker path (optional): Docker Engine 24+ and Docker Compose v2 —
  needs access to the Docker socket, which this machine currently denies.

## Quickstart (recommended: `mm.sh`)

From the repo root (`~/Documents/Code/media-manager`):

```bash
./mm.sh start    # launch API + web in the background (one-time venv/npm setup)
./mm.sh status   # check both processes
./mm.sh stop     # stop both
./mm.sh restart  # stop, then start
```

Then open the printed UI address (API health at `<api>/health`).

Port defaults: API `8001` (port `8000` is taken by another service on this
machine), web `5173`. If a default is busy, `mm.sh` automatically picks the
next free port and prints the actual addresses — or pin them explicitly:

```bash
MM_API_PORT=8001 MM_WEB_PORT=5174 ./mm.sh start
```

Pids/logs live in `.mm/` (gitignored); downloads and the SQLite DB persist in
`./data/`.

## Quickstart (Docker)

```bash
docker compose up --build
# web → http://localhost:5173
# api → http://localhost:8000/health
```

Downloads and the SQLite DB persist in `./data/` (`DOWNLOAD_DIR=/data/downloads`
inside the container).

## Local development (manual, without `mm.sh`)

```bash
# backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
DOWNLOAD_DIR=./data/downloads DATABASE_URL=sqlite:///./data/media-manager.db \
  PYTHONPATH=backend uvicorn app.main:app --reload --port 8001
# → http://localhost:8001/health

# run tests
PYTHONPATH=backend pytest backend/tests -q

# frontend (from ./frontend — vite must run with the frontend dir as cwd)
cd frontend
npm install
VITE_API_URL=http://localhost:8001 npm run dev
# → http://localhost:5173 (override the API address with VITE_API_URL)
```

## Configuration

Backend env vars:

| Var | Default | Purpose |
|-----|---------|---------|
| `DATABASE_URL` | `sqlite:///./data/media-manager.db` | SQLModel database |
| `DOWNLOAD_DIR` | `./data/downloads` (`/data/downloads` in Docker) | Download + thumbnail root |
| `MAX_CONCURRENT_JOBS` | `3` | Parallel download workers |
| `API_KEY` | *(empty = open)* | Required `X-API-Key` header when set |
| `YTDLP_BIN` | `yt-dlp` | yt-dlp executable |
| `YTDLP_COOKIES_FROM_BROWSER` | *(empty)* | e.g. `firefox` for cookie-gated sites |
| `FFMPEG_BIN` | `ffmpeg` | Used for thumbnails/chapters |

Frontend env vars (`frontend/.env`): `VITE_API_URL` (default
`http://localhost:8000`).

## API sketch

- `POST /jobs { url | urls[], source, destination }` · `GET /jobs[?status=]`
  · `GET /jobs/{id}` · `POST /jobs/{id}/retry` · `POST /jobs/{id}/cancel`
  · `DELETE /jobs/{id}`
- `GET /library[?q=&source=&tag=]` · `GET /library/{id}` ·
  `GET /library/{id}/file` (playback/download stream) ·
  `DELETE /library/{id}[?delete_file=true]`
- `GET /fs/roots` · `GET /fs/browse?path=` · `POST /fs/mkdir {path}`
- `POST /channels` · `GET /channels` · `PATCH /DELETE /channels/{id}` ·
  `POST /channels/{id}/check`
- `GET /settings` · `GET /files/...` (media playback) · `GET /health`

## Project structure

```
media-manager/
  backend/
    app/
      main.py            # FastAPI app + all routes
      models.py          # Job / Channel / LibraryItem tables
      jobs.py            # parallel asyncio worker queue
      library.py         # file indexing + ffmpeg thumbnails
      scheduler.py       # APScheduler channel checks
      auth.py / config.py / db.py
      scrapers/
        ytdlp_runner.py      # probe/build/run yt-dlp, parse progress
        playwright_runner.py # doodstream label (yt-dlp fallback)
    tests/               # pytest: routes + runner unit tests
    Dockerfile           # python + ffmpeg + yt-dlp
  frontend/
    src/
      pages/             # Queue / Library / Channels / Settings (dark UI)
      lib/api.ts         # typed API client + X-API-Key handling
    Dockerfile
  docker-compose.yml
```

## How it works

1. `POST /jobs` writes `queued` rows and pushes ids onto an `asyncio.Queue`.
2. N worker tasks pull ids, mark them `running`, and stream
   `yt-dlp --newline --progress` stdout, parsing `[download] NN%` lines into
   the `progress` column (the Queue page polls `GET /jobs` every 2s).
3. Before downloading, the runner probes `--flat-playlist -J` to decide
   between a single-file template and a playlist-folder template, then runs
   yt-dlp with metadata + resume flags.
4. On exit code 0, new files under the destination are indexed as
   `LibraryItem`s (video thumbnails via `ffmpeg -ss 1 -vframes 1`); on
   failure the job is marked `failed` with the tail of the error, retryable
   with resume.
5. Separately, APScheduler fires per-channel interval jobs that flat-list
   entries and enqueue unseen URLs.

## Roadmap

- Real Playwright DoodStream flow in `playwright_runner.py`
- Postgres swap via `DATABASE_URL`
- Per-job format/quality picker and cookie profiles in the UI
- Thumbnail serving over `/files` + richer tag editing
