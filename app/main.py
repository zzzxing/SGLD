from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.db import Base, engine, get_database_debug_info
from app.routers.api import router as api_router
from app.routers.web import router as web_router
from app.routers.ws import router as ws_router

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
def log_database_info() -> None:
    info = get_database_debug_info()
    print(f"[app] configured DATABASE_URL: {info['configured_url']}")
    print(f"[app] resolved DATABASE_URL:   {info['resolved_url']}")
    if info["sqlite_path"]:
        print(f"[app] sqlite file path:        {info['sqlite_path']}")
