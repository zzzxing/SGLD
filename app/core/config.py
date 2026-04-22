from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "追问智学"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "replace_me"
    database_url: str = "sqlite:///./data/app.db"
    upload_dir: str = "./data/uploads"
    parsed_dir: str = "./data/parsed"
    vector_dir: str = "./data/vectors"
    code_run_dir: str = "./data/code_runs"
    code_run_timeout: int = 3
    max_upload_mb: int = 20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
