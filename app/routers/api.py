from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.websocket_manager import ws_manager
from app.models import Chapter, KnowledgePoint, ModelProvider, QuestionStep, ResourceFile, StudyRecord, TeacherFeedback
from app.services.analytics_service import classroom_analytics
from app.services.classroom_service import (
    end_classroom_session,
    get_active_session,
    get_latest_session,
    pause_classroom_session,
    progress_with_question_chain,
    session_summary,
    start_classroom_session,
    teacher_dashboard_rows,
    update_code_result,
)
from app.services.code_runner_service import run_python_code
from app.services.content_service import ingest_resource_to_course
from app.services.llm_router_service import LLMRouterService
from app.services.prompt_service import get_prompt
from app.services.rag_service import retrieve_context_for_study
from app.services.settings_service import get_settings_map, upsert_setting
from app.services.upload_service import save_upload_file

router = APIRouter(prefix="/api")
llm_router = LLMRouterService()


def _require_role(request: Request, allowed: set[str]) -> None:
    role = request.session.get("role")
    if not role:
        raise HTTPException(status_code=401, detail="login required")
    if role not in allowed:
        raise HTTPException(status_code=403, detail="forbidden")


@router.get("/student/chapters")
def student_chapters(request: Request, db: Session = Depends(get_db)):
    _require_role(request, {"student"})
    chapters = db.query(Chapter).filter(Chapter.is_published.is_(True)).order_by(Chapter.id.asc()).all()
    return {"code": 0, "message": "ok", "data": [{"id": c.id, "title": c.title, "summary": c.summary} for c in chapters]}


@router.get("/student/current-session")
def student_current_session(request: Request, db: Session = Depends(get_db)):
    _require_role(request, {"student"})
    session = get_latest_session(db)
    if not session:
        return {"code": 0, "message": "ok", "data": {"status": "not_started"}}
    chapter = db.query(Chapter).filter(Chapter.id == session.chapter_id).first()
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "status": session.status,
            "session_id": session.id,
            "chapter_id": session.chapter_id,
            "chapter_title": chapter.title if chapter else "-",
            "started_at": session.started_at.isoformat(),
        },
    }


@router.post("/student/dialogue/answer")
async def student_answer(request: Request, study_record_id: int = Form(...), answer_text: str = Form(...), db: Session = Depends(get_db)):
    _require_role(request, {"student"})
    outcome = progress_with_question_chain(db, study_record_id=study_record_id, answer_text=answer_text)
    if not outcome:
        raise HTTPException(status_code=404, detail="study record not found")

    record = outcome["record"]
    step = outcome["step"]
    rag = retrieve_context_for_study(db, record, answer_text)
    ai_extra = llm_router.chat_with_db(
        db,
        messages=[
            {"role": "system", "content": get_prompt("student_system")},
            {"role": "user", "content": f"学生回答:{answer_text}\n\nRAG上下文:\n{rag.context_text[:1200]}"},
        ],
    )
    record.ai_reply = f"{outcome['message']}\n\n【RAG辅助】{ai_extra.content}"
    db.commit()

    await ws_manager.broadcast(
        f"teacher_session_{record.session_id}",
        {"type": "progress_update", "study_record_id": record.id, "progress_percent": record.progress_percent, "rag_hits": rag.hit_count},
    )

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "action": outcome["action"],
            "assistant_message": record.ai_reply,
            "progress_percent": record.progress_percent,
            "hint_level": record.hint_level,
            "step_no": step.step_no if step else None,
            "question_text": step.question_text if step else "本章节已完成",
            "rag_debug": {"hit_count": rag.hit_count, "sources": rag.sources, "used_fallback": rag.used_fallback},
        },
    }


@router.post("/student/code/run")
async def student_code_run(request: Request, study_record_id: int = Form(...), source_code: str = Form(...), db: Session = Depends(get_db)):
    _require_role(request, {"student"})
    run_result = run_python_code(source_code=source_code, timeout_sec=settings.code_run_timeout)
    record = db.query(StudyRecord).filter(StudyRecord.id == study_record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="study record not found")

    rag = retrieve_context_for_study(db, record, source_code)
    feedback = llm_router.chat_with_db(
        db,
        messages=[
            {"role": "system", "content": get_prompt("code_analysis")},
            {"role": "user", "content": f"代码:\n{source_code}\nstdout:{run_result['stdout']}\nstderr:{run_result['stderr']}\n\nRAG:\n{rag.context_text[:1000]}"},
        ],
    )

    updated = update_code_result(db, study_record_id=study_record_id, status=run_result["status"], error=run_result["stderr"])
    if not updated:
        raise HTTPException(status_code=404, detail="study record not found")
    await ws_manager.broadcast(f"teacher_session_{updated.session_id}", {"type": "code_update", "study_record_id": updated.id, "status": run_result["status"]})

    return {"code": 0, "message": "ok", "data": {**run_result, "assistant_feedback": feedback.content}}


@router.post("/teacher/classroom/start")
async def teacher_start_classroom(request: Request, chapter_id: int = Form(...), db: Session = Depends(get_db)):
    _require_role(request, {"teacher"})
    teacher_id = request.session.get("user_id")
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id, Chapter.is_published.is_(True)).first()
    if not chapter:
        raise HTTPException(status_code=400, detail="章节未发布，不能开始课堂")
    session = start_classroom_session(db, teacher_id=teacher_id, chapter_id=chapter_id)
    await ws_manager.broadcast("students_global", {"type": "classroom_status", "status": "active", "session_id": session.id, "chapter_id": chapter_id})
    return {"code": 0, "message": "ok", "data": {"session_id": session.id, "status": session.status}}


@router.post("/teacher/classroom/{session_id}/pause")
async def teacher_pause_classroom(request: Request, session_id: int, db: Session = Depends(get_db)):
    _require_role(request, {"teacher"})
    row = pause_classroom_session(db, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="session not found")
    await ws_manager.broadcast("students_global", {"type": "classroom_status", "status": "paused", "session_id": row.id, "chapter_id": row.chapter_id})
    return {"code": 0, "message": "ok", "data": {"session_id": row.id, "status": row.status}}


@router.post("/teacher/classroom/{session_id}/end")
async def teacher_end_classroom(request: Request, session_id: int, db: Session = Depends(get_db)):
    _require_role(request, {"teacher"})
    row = end_classroom_session(db, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="session not found")
    await ws_manager.broadcast("students_global", {"type": "classroom_status", "status": "ended", "session_id": row.id, "chapter_id": row.chapter_id})
    return {"code": 0, "message": "ok", "data": {"session_id": row.id, "status": row.status, "summary": session_summary(db, row.id)}}


@router.get("/teacher/classroom/{session_id}/dashboard")
def teacher_dashboard(request: Request, session_id: int, db: Session = Depends(get_db)):
    _require_role(request, {"teacher"})
    return {"code": 0, "message": "ok", "data": teacher_dashboard_rows(db, session_id=session_id)}


@router.get("/teacher/classroom/{session_id}/analytics")
def teacher_analytics(request: Request, session_id: int, db: Session = Depends(get_db)):
    _require_role(request, {"teacher"})
    data = classroom_analytics(db, session_id)
    data.update(session_summary(db, session_id))
    return {"code": 0, "message": "ok", "data": data}


@router.get("/teacher/students/{student_id}/detail")
def student_detail(request: Request, student_id: int, session_id: int, db: Session = Depends(get_db)):
    _require_role(request, {"teacher"})
    row = db.query(StudyRecord).filter(StudyRecord.session_id == session_id, StudyRecord.student_id == student_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="record not found")
    return {"code": 0, "message": "ok", "data": {"student_id": student_id, "recent_answer": row.student_answer, "recent_ai_reply": row.ai_reply, "progress_percent": row.progress_percent}}


@router.post("/teacher/feedbacks")
def create_feedback(request: Request, student_id: int = Form(...), session_id: int = Form(...), tag: str = Form(""), comment: str = Form(""), db: Session = Depends(get_db)):
    _require_role(request, {"teacher"})
    db.add(TeacherFeedback(student_id=student_id, session_id=session_id, tag=tag, comment=comment))
    db.commit()
    return {"code": 0, "message": "ok", "data": {"saved": True}}


@router.post("/teacher/resources/upload")
def upload_resource(request: Request, uploader_id: int = Form(...), course_id: int = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    _require_role(request, {"teacher"})
    cfg = get_settings_map(db)
    allowed = {x.strip().lower() for x in cfg.get("allowed_extensions", ".txt,.md,.pdf,.docx").split(",") if x.strip()}
    max_mb = int(cfg.get("max_upload_mb", str(settings.max_upload_mb)))
    path = save_upload_file(file, max_upload_mb=max_mb, allowed_extensions=allowed)
    ext = Path(file.filename or "").suffix.lower()
    row = ResourceFile(original_name=file.filename or "unknown", file_ext=ext, storage_path=path, uploader_id=uploader_id, parse_status="pending")
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"code": 0, "message": "uploaded", "data": {"resource_id": row.id, "course_id": course_id}}


@router.post("/teacher/resources/{resource_id}/parse")
def parse_resource(request: Request, resource_id: int, course_id: int = Form(...), db: Session = Depends(get_db)):
    _require_role(request, {"teacher"})
    return {"code": 0, "message": "parsed", "data": ingest_resource_to_course(db, resource_id=resource_id, course_id=course_id)}


@router.post("/teacher/chapters/{chapter_id}/publish")
def publish_chapter(request: Request, chapter_id: int, is_published: bool = Form(True), db: Session = Depends(get_db)):
    _require_role(request, {"teacher"})
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="chapter not found")
    chapter.is_published = is_published
    db.commit()
    return {"code": 0, "message": "ok", "data": {"chapter_id": chapter_id, "is_published": is_published}}


@router.get("/admin/model-providers")
def list_providers(request: Request, db: Session = Depends(get_db)):
    _require_role(request, {"admin"})
    providers = db.query(ModelProvider).order_by(ModelProvider.id.asc()).all()
    return {"code": 0, "message": "ok", "data": [{"id": p.id, "provider_name": p.provider_name, "model_name": p.model_name} for p in providers]}


@router.post("/admin/model-providers")
def add_provider(request: Request, provider_name: str = Form(...), model_name: str = Form(...), base_url: str = Form(""), api_key: str = Form(""), timeout_sec: int = Form(30), retry_times: int = Form(1), temperature: str = Form("0.3"), max_tokens: int = Form(512), enabled: bool = Form(True), is_default: bool = Form(False), db: Session = Depends(get_db)):
    _require_role(request, {"admin"})
    if is_default:
        db.query(ModelProvider).update({ModelProvider.is_default: False})
    row = ModelProvider(provider_name=provider_name, model_name=model_name, base_url=base_url, api_key=api_key, timeout_sec=timeout_sec, retry_times=retry_times, temperature=temperature, max_tokens=max_tokens, enabled=enabled, is_default=is_default)
    db.add(row)
    db.commit()
    return {"code": 0, "message": "ok", "data": {"id": row.id}}


@router.post("/admin/system-settings")
def save_system_settings(request: Request, max_upload_mb: str = Form(...), allowed_extensions: str = Form(...), classroom_safety_level: str = Form(...), default_temperature: str = Form(...), default_max_tokens: str = Form(...), default_timeout_sec: str = Form(...), db: Session = Depends(get_db)):
    _require_role(request, {"admin"})
    for k, v in {
        "max_upload_mb": max_upload_mb,
        "allowed_extensions": allowed_extensions,
        "classroom_safety_level": classroom_safety_level,
        "default_temperature": default_temperature,
        "default_max_tokens": default_max_tokens,
        "default_timeout_sec": default_timeout_sec,
    }.items():
        upsert_setting(db, k, v)
    return {"code": 0, "message": "ok", "data": {"saved": True}}


@router.get("/admin/system-settings")
def get_system_settings(request: Request, db: Session = Depends(get_db)):
    _require_role(request, {"admin"})
    return {"code": 0, "message": "ok", "data": get_settings_map(db)}
