import os

from sqlmodel import SQLModel, create_engine, Session

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./media-manager.db")

connect_args = {"check_same_thread": False, "timeout": 30} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


def init_db() -> None:
    from app.models import Channel, Job, LibraryItem  # noqa: F401

    SQLModel.metadata.create_all(engine)
    if DATABASE_URL.startswith("sqlite"):
        # WAL: readers (UI polling) never block writers (workers finishing
        # jobs) and vice versa — essential with parallel download workers.
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            # Lightweight migration: create_all() doesn't add columns to
            # existing tables, so backfill audio_only for older DBs.
            try:
                cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(job)").fetchall()]
                if "audio_only" not in cols:
                    conn.exec_driver_sql("ALTER TABLE job ADD COLUMN audio_only BOOLEAN DEFAULT 0 NOT NULL")
            except Exception:
                pass


def get_session():
    with Session(engine) as session:
        yield session
