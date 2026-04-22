from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Chapter, ClassroomSession, KnowledgePoint, QuestionStep, StudyRecord, User


HINT_TRIGGER_WORDS = ["不会", "不知道", "不懂", "没思路", "help"]


def get_latest_session(db: Session) -> ClassroomSession | None:
    return db.query(ClassroomSession).order_by(ClassroomSession.started_at.desc()).first()


def get_active_session(db: Session) -> ClassroomSession | None:
    return (
        db.query(ClassroomSession)
        .filter(ClassroomSession.status == "active")
        .order_by(ClassroomSession.started_at.desc())
        .first()
    )


def start_classroom_session(db: Session, teacher_id: int, chapter_id: int) -> ClassroomSession:
    latest = get_latest_session(db)
    if latest and latest.status in {"active", "paused"}:
        latest.status = "ended"
        latest.ended_at = datetime.utcnow()

    session = ClassroomSession(teacher_id=teacher_id, chapter_id=chapter_id, status="active")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def pause_classroom_session(db: Session, session_id: int) -> ClassroomSession | None:
    row = db.query(ClassroomSession).filter(ClassroomSession.id == session_id).first()
    if not row:
        return None
    if row.status == "active":
        row.status = "paused"
        db.commit()
        db.refresh(row)
    return row


def end_classroom_session(db: Session, session_id: int) -> ClassroomSession | None:
    row = db.query(ClassroomSession).filter(ClassroomSession.id == session_id).first()
    if not row:
        return None
    row.status = "ended"
    row.ended_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def _first_kp_and_step(db: Session, chapter_id: int) -> tuple[KnowledgePoint | None, QuestionStep | None]:
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.chapter_id == chapter_id).order_by(KnowledgePoint.order_no.asc()).first()
    if not kp:
        return None, None
    step = db.query(QuestionStep).filter(QuestionStep.knowledge_point_id == kp.id).order_by(QuestionStep.step_no.asc()).first()
    return kp, step


def ensure_study_record(db: Session, session_id: int, student_id: int, chapter_id: int) -> StudyRecord:
    record = db.query(StudyRecord).filter(StudyRecord.session_id == session_id, StudyRecord.student_id == student_id).first()
    if record:
        return record

    kp, step = _first_kp_and_step(db, chapter_id)
    record = StudyRecord(
        session_id=session_id,
        student_id=student_id,
        chapter_id=chapter_id,
        knowledge_point_id=kp.id if kp else None,
        question_step_id=step.id if step else None,
        progress_percent=0,
        hint_level=0,
        step_completed=False,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def touch_online(db: Session, session_id: int, student_id: int, is_online: bool) -> None:
    record = db.query(StudyRecord).filter(StudyRecord.session_id == session_id, StudyRecord.student_id == student_id).first()
    if not record:
        active = db.query(ClassroomSession).filter(ClassroomSession.id == session_id).first()
        if not active:
            return
        record = ensure_study_record(db, session_id=session_id, student_id=student_id, chapter_id=active.chapter_id)
    record.is_online = is_online
    record.last_seen_at = datetime.utcnow()
    db.commit()


def _next_step(db: Session, current_step: QuestionStep) -> tuple[KnowledgePoint | None, QuestionStep | None]:
    next_step = (
        db.query(QuestionStep)
        .filter(QuestionStep.knowledge_point_id == current_step.knowledge_point_id, QuestionStep.step_no > current_step.step_no)
        .order_by(QuestionStep.step_no.asc())
        .first()
    )
    if next_step:
        kp = db.query(KnowledgePoint).filter(KnowledgePoint.id == next_step.knowledge_point_id).first()
        return kp, next_step

    current_kp = db.query(KnowledgePoint).filter(KnowledgePoint.id == current_step.knowledge_point_id).first()
    if not current_kp:
        return None, None
    next_kp = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.chapter_id == current_kp.chapter_id, KnowledgePoint.order_no > current_kp.order_no)
        .order_by(KnowledgePoint.order_no.asc())
        .first()
    )
    if not next_kp:
        return None, None
    first_step = db.query(QuestionStep).filter(QuestionStep.knowledge_point_id == next_kp.id).order_by(QuestionStep.step_no.asc()).first()
    return next_kp, first_step


def progress_with_question_chain(db: Session, study_record_id: int, answer_text: str) -> dict | None:
    record = db.query(StudyRecord).filter(StudyRecord.id == study_record_id).first()
    if not record:
        return None

    step = db.query(QuestionStep).filter(QuestionStep.id == record.question_step_id).first() if record.question_step_id else None
    if not step:
        record.progress_percent = 100
        record.step_completed = True
        record.ai_reply = "本章节问题链已完成。"
        db.commit()
        db.refresh(record)
        return {"record": record, "action": "session_completed", "message": record.ai_reply, "step": None}

    lowered = answer_text.strip().lower()
    stuck = len(answer_text.strip()) < 8 or any(w in lowered for w in HINT_TRIGGER_WORDS)

    if stuck and record.hint_level < 3:
        record.hint_level += 1
        hints = {1: step.hint_level_1, 2: step.hint_level_2, 3: step.hint_level_3}
        reply = hints.get(record.hint_level) or "先回顾本步骤关键词。"
        action = "give_hint"
        record.step_completed = False
    else:
        record.step_completed = True
        record.hint_level = 0
        kp, next_step = _next_step(db, step)
        if next_step:
            record.knowledge_point_id = kp.id if kp else record.knowledge_point_id
            record.question_step_id = next_step.id
            reply = f"很好，进入下一步：{next_step.question_text}"
            action = "next_step"
        else:
            record.question_step_id = None
            reply = "你已完成本章节全部问题链步骤，准备总结。"
            action = "chapter_completed"

    record.student_answer = answer_text
    record.ai_reply = reply
    record.last_answer_at = datetime.utcnow()
    record.last_seen_at = datetime.utcnow()

    total_steps = db.query(QuestionStep).join(KnowledgePoint, KnowledgePoint.id == QuestionStep.knowledge_point_id).filter(KnowledgePoint.chapter_id == record.chapter_id).count()
    remaining = (
        db.query(QuestionStep)
        .join(KnowledgePoint, KnowledgePoint.id == QuestionStep.knowledge_point_id)
        .filter(KnowledgePoint.chapter_id == record.chapter_id, QuestionStep.id == record.question_step_id)
        .count()
    )
    completed = max(0, total_steps - remaining)
    record.progress_percent = int((completed / total_steps) * 100) if total_steps else 100

    db.commit()
    db.refresh(record)
    step_after = db.query(QuestionStep).filter(QuestionStep.id == record.question_step_id).first() if record.question_step_id else None
    return {"record": record, "action": action, "message": reply, "step": step_after}


def update_code_result(db: Session, study_record_id: int, status: str, error: str) -> StudyRecord | None:
    record = db.query(StudyRecord).filter(StudyRecord.id == study_record_id).first()
    if not record:
        return None
    record.last_code_status = status
    record.last_code_error = error[:1000]
    record.last_seen_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record


def session_summary(db: Session, session_id: int) -> dict:
    rows = db.query(StudyRecord).filter(StudyRecord.session_id == session_id).all()
    total = len(rows)
    if total == 0:
        return {"completion_rate": 0, "avg_hint_level": 0, "top_stuck_step": "-", "recent_active_students": 0}
    completion_rate = int(sum(1 for r in rows if r.progress_percent >= 100) / total * 100)
    avg_hint = round(sum(r.hint_level for r in rows) / total, 2)

    step_count: dict[str, int] = {}
    for r in rows:
        key = str(r.question_step_id or "完成")
        step_count[key] = step_count.get(key, 0) + (1 if r.progress_percent < 100 else 0)
    top_step = max(step_count, key=step_count.get) if step_count else "-"

    recent_cutoff = datetime.utcnow() - timedelta(minutes=10)
    active_students = len([r for r in rows if r.last_seen_at and r.last_seen_at >= recent_cutoff])
    return {
        "completion_rate": completion_rate,
        "avg_hint_level": avg_hint,
        "top_stuck_step": top_step,
        "recent_active_students": active_students,
    }


def teacher_dashboard_rows(db: Session, session_id: int) -> list[dict]:
    records = db.query(StudyRecord).filter(StudyRecord.session_id == session_id).all()
    users = {u.id: u for u in db.query(User).all()}
    chapter_map = {c.id: c for c in db.query(Chapter).all()}

    rows = []
    for r in records:
        rows.append(
            {
                "student_id": r.student_id,
                "student_name": users.get(r.student_id).full_name if users.get(r.student_id) else f"学生{r.student_id}",
                "is_online": r.is_online,
                "chapter_title": chapter_map.get(r.chapter_id).title if chapter_map.get(r.chapter_id) else "-",
                "last_answer_at": r.last_answer_at.strftime("%Y-%m-%d %H:%M:%S") if r.last_answer_at else "-",
                "progress_percent": r.progress_percent,
            }
        )
    rows.sort(key=lambda x: x["student_name"])
    return rows
