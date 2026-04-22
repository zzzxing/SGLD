from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.websocket_manager import ws_manager
from app.models import Chapter, Course, KnowledgePoint, ModelProvider, QuestionStep, ResourceFile, StudyRecord, TeacherFeedback, User
from app.services.analytics_service import classroom_analytics
from app.services.auth_service import authenticate_user
from app.services.classroom_service import (
    end_classroom_session,
    ensure_study_record,
    get_active_session,
    get_latest_session,
    pause_classroom_session,
    progress_with_question_chain,
    session_summary,
    teacher_dashboard_rows,
    update_code_result,
)
from app.services.code_runner_service import run_python_code
from app.services.content_service import ingest_resource_to_course
from app.services.llm_router_service import LLMRouterService
from app.services.prompt_service import get_prompt
from app.services.rag_service import retrieve_context_for_study
from app.services.settings_service import get_settings_map, upsert_setting

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def current_role(request: Request) -> str | None:
    return request.session.get("role")


def current_user_id(request: Request) -> int | None:
    return request.session.get("user_id")


def require_role_web(request: Request, roles: set[str]) -> None:
    role = current_role(request)
    if not role:
        raise HTTPException(status_code=401, detail="login required")
    if role not in roles:
        raise HTTPException(status_code=403, detail="forbidden")


@router.get("/")
def index(request: Request):
    role = current_role(request)
    if role == "student":
        return RedirectResponse("/student/home", 302)
    if role == "teacher":
        return RedirectResponse("/teacher/home", 302)
    if role == "admin":
        return RedirectResponse("/admin/home", 302)
    return RedirectResponse("/login", 302)


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request, "error": ""})


@router.post("/login")
def do_login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = authenticate_user(db, username=username, password=password)
    if not user:
        return templates.TemplateResponse("auth/login.html", {"request": request, "error": "用户名或密码错误"})
    request.session["user_id"] = user.id
    request.session["role"] = user.role
    return RedirectResponse("/", 302)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", 302)


@router.get("/student/home")
def student_home(request: Request, db: Session = Depends(get_db)):
    require_role_web(request, {"student"})
    courses = db.query(Course).all()
    latest = get_latest_session(db)
    status = "not_started"
    current_status = None
    if latest:
        chapter = db.query(Chapter).filter(Chapter.id == latest.chapter_id).first()
        status = latest.status
        current_status = {
            "session_id": latest.id,
            "chapter_title": chapter.title if chapter else "-",
            "started_at": latest.started_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
    return templates.TemplateResponse("student/home.html", {"request": request, "courses": courses, "current_status": current_status, "class_status": status})


@router.get("/student/chapter/{chapter_id}")
def student_chapter(request: Request, chapter_id: int, db: Session = Depends(get_db)):
    require_role_web(request, {"student"})
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id, Chapter.is_published.is_(True)).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="chapter not found or unpublished")

    latest = get_latest_session(db)
    class_status = latest.status if latest else "not_started"
    study_record = None
    current_step = None
    current_kp = None
    summary = None

    if latest and latest.chapter_id == chapter_id and latest.status in {"active", "paused", "ended"}:
        study_record = ensure_study_record(db, session_id=latest.id, student_id=current_user_id(request), chapter_id=chapter_id)
        if study_record.question_step_id:
            current_step = db.query(QuestionStep).filter(QuestionStep.id == study_record.question_step_id).first()
        if study_record.knowledge_point_id:
            current_kp = db.query(KnowledgePoint).filter(KnowledgePoint.id == study_record.knowledge_point_id).first()
        if latest.status == "ended":
            summary = session_summary(db, latest.id)

    return templates.TemplateResponse(
        "student/chapter.html",
        {
            "request": request,
            "chapter": chapter,
            "active_session": latest,
            "class_status": class_status,
            "study_record": study_record,
            "current_step": current_step,
            "current_kp": current_kp,
            "summary": summary,
            "user_id": current_user_id(request),
        },
    )


@router.get("/teacher/home")
def teacher_home(request: Request, db: Session = Depends(get_db)):
    require_role_web(request, {"teacher"})
    courses = db.query(Course).all()
    chapters = db.query(Chapter).order_by(Chapter.id.desc()).all()
    resources = db.query(ResourceFile).order_by(ResourceFile.id.desc()).all()
    kps = db.query(KnowledgePoint).order_by(KnowledgePoint.id.desc()).limit(10).all()
    steps = db.query(QuestionStep).order_by(QuestionStep.id.desc()).limit(10).all()
    latest = get_latest_session(db)
    dashboard_rows = teacher_dashboard_rows(db, latest.id) if latest else []
    analytics = classroom_analytics(db, latest.id) if latest else None
    lifecycle_summary = session_summary(db, latest.id) if latest and latest.status == "ended" else None

    return templates.TemplateResponse(
        "teacher/home.html",
        {
            "request": request,
            "courses": courses,
            "chapters": chapters,
            "resources": resources,
            "kps": kps,
            "steps": steps,
            "active_session": latest,
            "dashboard_rows": dashboard_rows,
            "analytics": analytics,
            "lifecycle_summary": lifecycle_summary,
            "students": db.query(User).filter(User.role == "student").all(),
            "user_id": current_user_id(request),
        },
    )


@router.post("/teacher/classroom/{session_id}/pause")
async def teacher_pause(request: Request, session_id: int, db: Session = Depends(get_db)):
    require_role_web(request, {"teacher"})
    row = pause_classroom_session(db, session_id)
    if row:
        await ws_manager.broadcast("students_global", {"type": "classroom_status", "status": "paused", "session_id": row.id, "chapter_id": row.chapter_id})
        return RedirectResponse("/teacher/home", 302)
    raise HTTPException(status_code=404, detail="session not found")


@router.post("/teacher/classroom/{session_id}/end")
async def teacher_end(request: Request, session_id: int, db: Session = Depends(get_db)):
    require_role_web(request, {"teacher"})
    row = end_classroom_session(db, session_id)
    if row:
        await ws_manager.broadcast("students_global", {"type": "classroom_status", "status": "paused", "session_id": row.id, "chapter_id": row.chapter_id})
        return RedirectResponse("/teacher/home", 302)
    raise HTTPException(status_code=404, detail="session not found")


@router.get("/teacher/student/{student_id}")
def teacher_student_detail(request: Request, student_id: int, session_id: int, db: Session = Depends(get_db)):
    require_role_web(request, {"teacher"})
    row = db.query(StudyRecord).filter(StudyRecord.session_id == session_id, StudyRecord.student_id == student_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="student record not found")
    chapter = db.query(Chapter).filter(Chapter.id == row.chapter_id).first()
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.id == row.knowledge_point_id).first() if row.knowledge_point_id else None
    step = db.query(QuestionStep).filter(QuestionStep.id == row.question_step_id).first() if row.question_step_id else None
    feedback = db.query(TeacherFeedback).filter(TeacherFeedback.session_id == session_id, TeacherFeedback.student_id == student_id).order_by(TeacherFeedback.id.desc()).first()
    return templates.TemplateResponse("teacher/student_detail.html", {"request": request, "session_id": session_id, "student": db.query(User).filter(User.id == student_id).first(), "record": row, "chapter": chapter, "kp": kp, "step": step, "feedback": feedback})


@router.post("/teacher/student/{student_id}/feedback")
def teacher_feedback_save(request: Request, student_id: int, session_id: int = Form(...), tag: str = Form(""), comment: str = Form(""), db: Session = Depends(get_db)):
    require_role_web(request, {"teacher"})
    db.add(TeacherFeedback(student_id=student_id, session_id=session_id, tag=tag, comment=comment))
    db.commit()
    return RedirectResponse(f"/teacher/student/{student_id}?session_id={session_id}", 302)


@router.post("/teacher/resources/{resource_id}/parse")
def parse_resource_web(request: Request, resource_id: int, course_id: int = Form(...), db: Session = Depends(get_db)):
    require_role_web(request, {"teacher"})
    ingest_resource_to_course(db, resource_id=resource_id, course_id=course_id)
    return RedirectResponse("/teacher/home", 302)


@router.post("/teacher/chapter/{chapter_id}/publish")
def publish_chapter_web(request: Request, chapter_id: int, db: Session = Depends(get_db)):
    require_role_web(request, {"teacher"})
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="chapter not found")
    chapter.is_published = not chapter.is_published
    db.commit()
    return RedirectResponse("/teacher/home", 302)


@router.post("/teacher/chapter/{chapter_id}/edit")
def edit_chapter_web(request: Request, chapter_id: int, explanation: str = Form(...), db: Session = Depends(get_db)):
    require_role_web(request, {"teacher"})
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if chapter:
        chapter.explanation = explanation
        db.commit()
    return RedirectResponse("/teacher/home", 302)


@router.post("/teacher/kp/{kp_id}/edit")
def edit_kp_web(request: Request, kp_id: int, title: str = Form(...), content: str = Form(""), db: Session = Depends(get_db)):
    require_role_web(request, {"teacher"})
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.id == kp_id).first()
    if kp:
        kp.title = title
        kp.content = content
        db.commit()
    return RedirectResponse("/teacher/home", 302)


@router.post("/teacher/step/{step_id}/edit")
def edit_step_web(request: Request, step_id: int, question_text: str = Form(...), hint1: str = Form(""), hint2: str = Form(""), hint3: str = Form(""), db: Session = Depends(get_db)):
    require_role_web(request, {"teacher"})
    step = db.query(QuestionStep).filter(QuestionStep.id == step_id).first()
    if step:
        step.question_text = question_text
        step.hint_level_1 = hint1
        step.hint_level_2 = hint2
        step.hint_level_3 = hint3
        db.commit()
    return RedirectResponse("/teacher/home", 302)


@router.get("/teacher/dashboard-fragment")
def teacher_dashboard_fragment(request: Request, session_id: int, db: Session = Depends(get_db)):
    require_role_web(request, {"teacher"})
    rows = teacher_dashboard_rows(db, session_id)
    return templates.TemplateResponse("teacher/_dashboard_table.html", {"request": request, "dashboard_rows": rows, "session_id": session_id})


@router.get("/teacher/analytics-fragment")
def teacher_analytics_fragment(request: Request, session_id: int, db: Session = Depends(get_db)):
    require_role_web(request, {"teacher"})
    data = classroom_analytics(db, session_id)
    data.update(session_summary(db, session_id))
    return templates.TemplateResponse("teacher/_analytics.html", {"request": request, "a": data})


@router.get("/admin/home")
def admin_home(request: Request, db: Session = Depends(get_db)):
    require_role_web(request, {"admin"})
    providers = db.query(ModelProvider).order_by(ModelProvider.id.asc()).all()
    settings_map = get_settings_map(db)
    return templates.TemplateResponse("admin/home.html", {"request": request, "providers": providers, "settings": settings_map})


@router.post("/admin/provider/add")
def admin_provider_add(request: Request, provider_name: str = Form(...), model_name: str = Form(...), base_url: str = Form(""), api_key: str = Form(""), timeout_sec: int = Form(30), retry_times: int = Form(1), temperature: str = Form("0.3"), max_tokens: int = Form(512), enabled: bool = Form(True), is_default: bool = Form(False), db: Session = Depends(get_db)):
    require_role_web(request, {"admin"})
    if is_default:
        db.query(ModelProvider).update({ModelProvider.is_default: False})
    db.add(ModelProvider(provider_name=provider_name, model_name=model_name, base_url=base_url, api_key=api_key, timeout_sec=timeout_sec, retry_times=retry_times, temperature=temperature, max_tokens=max_tokens, enabled=enabled, is_default=is_default))
    db.commit()
    return RedirectResponse("/admin/home", 302)


@router.post("/admin/provider/{provider_id}/edit")
def admin_provider_edit(request: Request, provider_id: int, provider_name: str = Form(...), model_name: str = Form(...), base_url: str = Form(""), api_key: str = Form(""), timeout_sec: int = Form(30), retry_times: int = Form(1), temperature: str = Form("0.3"), max_tokens: int = Form(512), db: Session = Depends(get_db)):
    require_role_web(request, {"admin"})
    row = db.query(ModelProvider).filter(ModelProvider.id == provider_id).first()
    if row:
        row.provider_name = provider_name
        row.model_name = model_name
        row.base_url = base_url
        row.api_key = api_key
        row.timeout_sec = timeout_sec
        row.retry_times = retry_times
        row.temperature = temperature
        row.max_tokens = max_tokens
        db.commit()
    return RedirectResponse("/admin/home", 302)


@router.post("/admin/provider/{provider_id}/toggle")
def admin_provider_toggle(request: Request, provider_id: int, db: Session = Depends(get_db)):
    require_role_web(request, {"admin"})
    row = db.query(ModelProvider).filter(ModelProvider.id == provider_id).first()
    if row:
        row.enabled = not row.enabled
        db.commit()
    return RedirectResponse("/admin/home", 302)


@router.post("/admin/provider/{provider_id}/default")
def admin_provider_default(request: Request, provider_id: int, db: Session = Depends(get_db)):
    require_role_web(request, {"admin"})
    row = db.query(ModelProvider).filter(ModelProvider.id == provider_id).first()
    if row:
        db.query(ModelProvider).update({ModelProvider.is_default: False})
        row.is_default = True
        db.commit()
    return RedirectResponse("/admin/home", 302)


@router.post("/admin/settings/save")
def admin_save_settings(request: Request, max_upload_mb: str = Form(...), allowed_extensions: str = Form(...), classroom_safety_level: str = Form(...), default_temperature: str = Form(...), default_max_tokens: str = Form(...), default_timeout_sec: str = Form(...), db: Session = Depends(get_db)):
    require_role_web(request, {"admin"})
    for key, value in {"max_upload_mb": max_upload_mb, "allowed_extensions": allowed_extensions, "classroom_safety_level": classroom_safety_level, "default_temperature": default_temperature, "default_max_tokens": default_max_tokens, "default_timeout_sec": default_timeout_sec}.items():
        upsert_setting(db, key, value)
    return RedirectResponse("/admin/home", 302)


@router.post("/student/dialogue")
async def student_dialogue_fragment(request: Request, answer_text: str = Form(...), study_record_id: int = Form(...), db: Session = Depends(get_db)):
    require_role_web(request, {"student"})
    outcome = progress_with_question_chain(db, study_record_id=study_record_id, answer_text=answer_text)
    if not outcome:
        raise HTTPException(status_code=404, detail="study record not found")

    record = outcome["record"]
    rag = retrieve_context_for_study(db, record, answer_text)
    extra = LLMRouterService().chat_with_db(db, messages=[{"role": "system", "content": get_prompt("student_system")}, {"role": "user", "content": f"答复:{answer_text}\n\n上下文:{rag.context_text[:800]}"}])
    record.ai_reply = f"{outcome['message']}\n\n{extra.content}"
    db.commit()

    await ws_manager.broadcast(f"teacher_session_{record.session_id}", {"type": "progress_update", "study_record_id": record.id, "progress_percent": record.progress_percent, "rag_hits": rag.hit_count, "rag_fallback": rag.used_fallback})

    step = outcome["step"]
    return templates.TemplateResponse("student/_ai_reply.html", {"request": request, "message": record.ai_reply, "provider": "router", "model": "dynamic", "progress_percent": record.progress_percent, "hint_level": record.hint_level, "question_text": step.question_text if step else "章节已完成", "action": outcome["action"], "rag_hit_count": rag.hit_count, "rag_sources": ", ".join(rag.sources[:3]), "rag_fallback": rag.used_fallback})


@router.post("/student/code/run")
async def student_code_run_fragment(request: Request, source_code: str = Form(...), study_record_id: int = Form(...), db: Session = Depends(get_db)):
    require_role_web(request, {"student"})
    result = run_python_code(source_code=source_code)
    record = db.query(StudyRecord).filter(StudyRecord.id == study_record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="study record not found")
    rag = retrieve_context_for_study(db, record, source_code)
    feedback = LLMRouterService().chat_with_db(db, messages=[{"role": "system", "content": get_prompt("code_analysis")}, {"role": "user", "content": f"代码\n{source_code}\nstdout={result['stdout']}\nstderr={result['stderr']}\nRAG={rag.context_text[:500]}"}])

    updated = update_code_result(db, study_record_id=study_record_id, status=result["status"], error=result["stderr"])
    if updated:
        await ws_manager.broadcast(f"teacher_session_{updated.session_id}", {"type": "code_update", "study_record_id": updated.id, "status": result["status"]})

    return templates.TemplateResponse("student/_code_reply.html", {"request": request, "result": result, "assistant_feedback": feedback.content, "rag_hit_count": rag.hit_count, "rag_sources": ", ".join(rag.sources[:3]), "rag_fallback": rag.used_fallback})
