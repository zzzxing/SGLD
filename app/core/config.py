from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    app_name: str = "追问智学"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "replace_me"
    database_url: str = f"sqlite:///{(DATA_ROOT / 'app.db').as_posix()}"
    upload_dir: str = str((DATA_ROOT / "uploads").as_posix())
    parsed_dir: str = str((DATA_ROOT / "parsed").as_posix())
    vector_dir: str = str((DATA_ROOT / "vectors").as_posix())
    code_run_dir: str = str((DATA_ROOT / "code_runs").as_posix())
    code_run_timeout: int = 3
    max_upload_mb: int = 20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
