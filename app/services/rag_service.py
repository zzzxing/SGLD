from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import DocumentChunk, StudyRecord


@dataclass
class RagResult:
    context_text: str
    hit_count: int
    sources: list[str]
    used_fallback: bool


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in text.replace("\n", " ").split() if token.strip()}


def retrieve_context_for_study(db: Session, study_record: StudyRecord, user_text: str, top_k: int = 4) -> RagResult:
    query_tokens = _tokenize(user_text)

    candidates: list[DocumentChunk] = []

    # 1) 当前章节
    candidates.extend(
        db.query(DocumentChunk)
        .filter(DocumentChunk.chapter_id == study_record.chapter_id)
        .order_by(DocumentChunk.chunk_index.asc())
        .limit(80)
        .all()
    )

    # 2) 当前知识点
    if study_record.knowledge_point_id:
        candidates.extend(
            db.query(DocumentChunk)
            .filter(DocumentChunk.knowledge_point_id == study_record.knowledge_point_id)
            .order_by(DocumentChunk.chunk_index.asc())
            .limit(40)
            .all()
        )

    # 3) 当前步骤
    if study_record.question_step_id:
        candidates.extend(
            db.query(DocumentChunk)
            .filter(DocumentChunk.question_step_id == study_record.question_step_id)
            .order_by(DocumentChunk.chunk_index.asc())
            .limit(20)
            .all()
        )

    # 4) 课程内其他内容（仅补充）
    if not candidates:
        candidates = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.course_id.isnot(None))
            .order_by(DocumentChunk.id.desc())
            .limit(40)
            .all()
        )

    scored = []
    for c in candidates:
        tokens = _tokenize(c.chunk_text)
        score = len(query_tokens & tokens) if query_tokens else 0
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [c for score, c in scored[:top_k] if score > 0]

    used_fallback = False
    if not selected:
        selected = [c for _, c in scored[:top_k]]
        used_fallback = True

    context_text = "\n\n".join([f"[{c.source_label}] {c.chunk_text}" for c in selected])
    sources = [c.source_label for c in selected]

    return RagResult(
        context_text=context_text,
        hit_count=len(selected),
        sources=sources,
        used_fallback=used_fallback,
    )
