from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.db import Base, engine
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
