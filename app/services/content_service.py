from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from app.models import Chapter, DocumentChunk, KnowledgePoint, QuestionStep, ResourceFile

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _read_txt_md(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf(path: Path) -> tuple[str, str]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return "", "missing_dependency:pypdf"

    try:
        reader = PdfReader(str(path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return text, "ok"
    except Exception as exc:
        return "", f"pdf_parse_error:{exc}"


def _read_docx(path: Path) -> tuple[str, str]:
    try:
        from docx import Document  # type: ignore
    except Exception:
        return "", "missing_dependency:python-docx"

    try:
        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return text, "ok"
    except Exception as exc:
        return "", f"docx_parse_error:{exc}"


def parse_text_from_resource(resource: ResourceFile) -> tuple[str, str]:
    path = Path(resource.storage_path)
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return _read_txt_md(path), "ok"
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix == ".docx":
        return _read_docx(path)
    return "", f"unsupported:{suffix}"


def split_sections(text: str) -> list[tuple[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    sections: list[tuple[str, str]] = []
    current_title = "自动章节1"
    bucket: list[str] = []

    def flush() -> None:
        nonlocal bucket, current_title
        if bucket:
            sections.append((current_title, "\n".join(bucket)))
            bucket = []

    for line in lines:
        if line.startswith("#"):
            flush()
            current_title = line.lstrip("#").strip() or "未命名章节"
        else:
            bucket.append(line)
    flush()

    if not sections and text.strip():
        sections = [("自动章节1", text[:1600])]
    return sections[:8]


def generate_kps(section_text: str) -> list[str]:
    sentences = [s.strip() for s in section_text.replace("。", "\n").splitlines() if s.strip()]
    kps = []
    for sentence in sentences[:4]:
        short = sentence[:30]
        kps.append(short if len(short) > 4 else f"知识点：{short}")
    return kps or ["核心概念", "关键操作", "常见错误"]


def generate_question_steps(kp_title: str) -> list[dict]:
    return [
        {
            "question_text": f"你如何理解“{kp_title}”？请先用自己的话描述。",
            "hint1": "先说定义，不要求完整。",
            "hint2": "想想它在本章节中的作用。",
            "hint3": "可以结合一个最简单例子。",
        },
        {
            "question_text": f"如果把“{kp_title}”用在练习里，第一步应做什么？",
            "hint1": "先确定输入和输出。",
            "hint2": "再写出关键语句骨架。",
            "hint3": "最后检查是否符合题目要求。",
        },
    ]


def _save_chunks(db: "Session", *, resource_id: int, course_id: int, chapter_id: int, chapter_text: str, source_label: str) -> int:
    chunk_size = 220
    idx = 0
    created = 0
    while idx < len(chapter_text):
        piece = chapter_text[idx : idx + chunk_size].strip()
        if piece:
            db.add(
                DocumentChunk(
                    resource_id=resource_id,
                    course_id=course_id,
                    chapter_id=chapter_id,
                    source_label=source_label,
                    chunk_text=piece,
                    chunk_index=created,
                )
            )
            created += 1
        idx += chunk_size
    return created


def ingest_resource_to_course(db: "Session", *, resource_id: int, course_id: int) -> dict:
    resource = db.query(ResourceFile).filter(ResourceFile.id == resource_id).first()
    if not resource:
        raise ValueError("resource not found")

    text, status = parse_text_from_resource(resource)
    if not text.strip():
        resource.parse_status = "failed"
        resource.parse_message = status
        resource.extracted_text_len = 0
        resource.generated_chapter_count = 0
        resource.last_processed_at = datetime.utcnow()
        db.commit()
        return {"chapters": 0, "knowledge_points": 0, "question_steps": 0, "chunks": 0, "status": "failed"}

    sections = split_sections(text)
    created_chapters = 0
    created_kps = 0
    created_steps = 0
    created_chunks = 0

    for idx, (section_title, section_content) in enumerate(sections, start=1):
        chapter = Chapter(
            course_id=course_id,
            title=section_title,
            summary=section_content[:180],
            explanation=f"【章节讲解】{section_title}\n{section_content[:320]}",
            order_no=idx,
            is_published=False,
        )
        db.add(chapter)
        db.flush()
        created_chapters += 1

        created_chunks += _save_chunks(
            db,
            resource_id=resource.id,
            course_id=course_id,
            chapter_id=chapter.id,
            chapter_text=section_content,
            source_label=f"{resource.original_name}:{section_title}",
        )

        for kp_idx, kp_title in enumerate(generate_kps(section_content), start=1):
            kp = KnowledgePoint(chapter_id=chapter.id, title=kp_title, content=f"围绕“{kp_title}”进行理解与练习。", order_no=kp_idx)
            db.add(kp)
            db.flush()
            created_kps += 1

            for step_no, step in enumerate(generate_question_steps(kp_title), start=1):
                db.add(
                    QuestionStep(
                        knowledge_point_id=kp.id,
                        step_no=step_no,
                        question_text=step["question_text"],
                        hint_level_1=step["hint1"],
                        hint_level_2=step["hint2"],
                        hint_level_3=step["hint3"],
                    )
                )
                created_steps += 1

    resource.parse_status = "success" if status == "ok" else "partial"
    resource.parse_message = status
    resource.extracted_text_len = len(text)
    resource.generated_chapter_count = created_chapters
    resource.last_processed_at = datetime.utcnow()
    resource.parsed_summary = f"章节{created_chapters}，知识点{created_kps}，问题步骤{created_steps}，切片{created_chunks}"
    db.commit()
    return {
        "chapters": created_chapters,
        "knowledge_points": created_kps,
        "question_steps": created_steps,
        "chunks": created_chunks,
        "status": resource.parse_status,
    }
