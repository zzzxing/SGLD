from sqlalchemy.orm import Session

from app.models import SystemConfig

DEFAULT_SETTINGS = {
    "max_upload_mb": "20",
    "allowed_extensions": ".txt,.md,.pdf,.docx",
    "classroom_safety_level": "strict",
    "default_temperature": "0.3",
    "default_max_tokens": "512",
    "default_timeout_sec": "30",
}


def get_settings_map(db: Session) -> dict[str, str]:
    current = {row.key: row.value for row in db.query(SystemConfig).all()}
    for k, v in DEFAULT_SETTINGS.items():
        current.setdefault(k, v)
    return current


def upsert_setting(db: Session, key: str, value: str) -> None:
    row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if row:
        row.value = value
    else:
        db.add(SystemConfig(key=key, value=value))
    db.commit()
