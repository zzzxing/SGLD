from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.db import Base, SessionLocal, engine, get_database_debug_info
from app.routers.api import router as api_router
from app.routers.web import router as web_router
from app.routers.ws import router as ws_router
from app.services.bootstrap_seed_service import seed_demo_data, should_seed_demo_data

for p in [settings.upload_dir, settings.parsed_dir, settings.vector_dir, settings.code_run_dir]:
    Path(p).mkdir(parents=True, exist_ok=True)

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(web_router)
app.include_router(api_router)
app.include_router(ws_router)


@app.on_event("startup")
def app_startup() -> None:
    info = get_database_debug_info()
    print(f"[app] configured DATABASE_URL: {info['configured_url']}")
    print(f"[app] resolved DATABASE_URL:   {info['resolved_url']}")
    if info["sqlite_path"]:
        print(f"[app] sqlite file path:        {info['sqlite_path']}")

    db = SessionLocal()
    try:
        if should_seed_demo_data(db):
            print("[app] database is empty, seeding demo data...")
            seed_demo_data(db)
            print("[app] demo data seeded")
        else:
            print("[app] existing data found, skip demo seeding")
    finally:
        db.close()
