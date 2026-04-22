import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.db import SessionLocal, get_database_debug_info
from app.services.bootstrap_seed_service import seed_demo_data


def main() -> None:
    info = get_database_debug_info()
    print(f"[seed] configured DATABASE_URL: {info['configured_url']}")
    print(f"[seed] resolved DATABASE_URL:   {info['resolved_url']}")
    if info["sqlite_path"]:
        print(f"[seed] sqlite file path:        {info['sqlite_path']}")

    db = SessionLocal()
    try:
        seed_demo_data(db)
        print("[seed] seed done")
    finally:
        db.close()


if __name__ == "__main__":
    main()
