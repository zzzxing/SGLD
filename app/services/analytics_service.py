from collections import Counter

from sqlalchemy.orm import Session

from app.models import Chapter, QuestionStep, StudyRecord


def classroom_analytics(db: Session, session_id: int) -> dict:
    rows = db.query(StudyRecord).filter(StudyRecord.session_id == session_id).all()
    total = len(rows)
    if total == 0:
        return {
            "completion_rate": 0,
            "online_count": 0,
            "chapter_distribution": {},
            "top_stuck_step": "-",
            "hint_distribution": {"hint0": 0, "hint1": 0, "hint2": 0, "hint3": 0},
        }

    completed = sum(1 for r in rows if r.progress_percent >= 100)
    online_count = sum(1 for r in rows if r.is_online)

    chapter_map = {c.id: c.title for c in db.query(Chapter).all()}
    chapter_counter = Counter(chapter_map.get(r.chapter_id, "-") for r in rows)

    step_map = {s.id: f"KP{s.knowledge_point_id}-Step{s.step_no}" for s in db.query(QuestionStep).all()}
    stuck_counter = Counter(step_map.get(r.question_step_id, "已完成") for r in rows if r.progress_percent < 100)
    top_stuck = stuck_counter.most_common(1)[0][0] if stuck_counter else "-"

    hint_counter = Counter(r.hint_level for r in rows)

    return {
        "completion_rate": int((completed / total) * 100),
        "online_count": online_count,
        "chapter_distribution": dict(chapter_counter),
        "top_stuck_step": top_stuck,
        "hint_distribution": {
            "hint0": hint_counter.get(0, 0),
            "hint1": hint_counter.get(1, 0),
            "hint2": hint_counter.get(2, 0),
            "hint3": hint_counter.get(3, 0),
        },
    }
