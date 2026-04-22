from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings

DEFAULT_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md"}


def save_upload_file(upload: UploadFile, *, max_upload_mb: int | None = None, allowed_extensions: set[str] | None = None) -> str:
    ext = Path(upload.filename or "").suffix.lower()
    allowed = allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS
    if ext not in allowed:
        raise ValueError(f"不支持的文件类型: {ext}")

    target_dir = Path(settings.upload_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{uuid4().hex}{ext}"

    content = upload.file.read()
    limit_mb = max_upload_mb if max_upload_mb is not None else settings.max_upload_mb
    max_size = int(limit_mb) * 1024 * 1024
    if len(content) > max_size:
        raise ValueError("文件超过大小限制")

    target_path.write_bytes(content)
    return str(target_path)
