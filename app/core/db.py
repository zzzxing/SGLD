from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_sqlite_url(database_url: str) -> tuple[str, Path | None]:
    """Resolve sqlite URLs to stable absolute path and ensure parent dir exists."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return database_url, None

    db_name = url.database
    if not db_name or db_name == ":memory:":
        return database_url, None

    db_path = Path(db_name)
    if not db_path.is_absolute():
        db_path = (PROJECT_ROOT / db_path).resolve()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_url = url.set(database=str(db_path)).render_as_string(hide_password=False)
    return resolved_url, db_path


DATABASE_URL, SQLITE_DB_PATH = _resolve_sqlite_url(settings.database_url)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_database_debug_info() -> dict[str, str | None]:
    return {
        "configured_url": settings.database_url,
        "resolved_url": DATABASE_URL,
        "sqlite_path": str(SQLITE_DB_PATH) if SQLITE_DB_PATH else None,
    }


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
