import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import models  # noqa: F401  # ensure table metadata is loaded
from app.core.db import Base, engine, get_database_debug_info


def main() -> None:
    info = get_database_debug_info()
    print(f"[init_db] configured DATABASE_URL: {info['configured_url']}")
    print(f"[init_db] resolved DATABASE_URL:   {info['resolved_url']}")
    if info["sqlite_path"]:
        print(f"[init_db] sqlite file path:        {info['sqlite_path']}")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("[init_db] database re-initialized")


if __name__ == "__main__":
    main()
