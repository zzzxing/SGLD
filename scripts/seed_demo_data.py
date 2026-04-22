import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session

from app.core.db import SessionLocal, get_database_debug_info
from app.core.security import hash_password
from app.models import Chapter, Course, KnowledgePoint, ModelProvider, QuestionStep, SystemConfig, User


def seed_users(db: Session) -> None:
    users = [
        ("admin", "系统管理员", "admin"),
        ("teacher1", "张老师", "teacher"),
        ("student1", "学生一号", "student"),
        ("student2", "学生二号", "student"),
    ]
    for username, full_name, role in users:
        if db.query(User).filter(User.username == username).first():
            continue
        db.add(User(username=username, full_name=full_name, role=role, hashed_password=hash_password("123456")))
    db.commit()


def seed_course_content(db: Session) -> None:
    teacher = db.query(User).filter(User.username == "teacher1").first()
    if not teacher:
        return

    course = db.query(Course).filter(Course.title == "Python 程序设计基础").first()
    if not course:
        course = Course(title="Python 程序设计基础", description="面向初中信息技术课堂示范课", teacher_id=teacher.id)
        db.add(course)
        db.commit()
        db.refresh(course)

    chapter = db.query(Chapter).filter(Chapter.course_id == course.id, Chapter.title == "输入、输出与变量").first()
    if not chapter:
        chapter = Chapter(
            course_id=course.id,
            title="输入、输出与变量",
            summary="这是示范章节。",
            explanation="变量用于保存数据，input 用于输入，print 用于输出。",
            order_no=1,
            is_published=True,
        )
        db.add(chapter)
        db.commit()
        db.refresh(chapter)

    kp = db.query(KnowledgePoint).filter(KnowledgePoint.chapter_id == chapter.id).first()
    if not kp:
        kp = KnowledgePoint(chapter_id=chapter.id, title="变量与输入输出", content="理解 input/print/变量关系", order_no=1)
        db.add(kp)
        db.commit()
        db.refresh(kp)

    if not db.query(QuestionStep).filter(QuestionStep.knowledge_point_id == kp.id).first():
        db.add_all(
            [
                QuestionStep(
                    knowledge_point_id=kp.id,
                    step_no=1,
                    question_text="为什么 input() 的结果通常要先保存到变量？",
                    hint_level_1="想想后面是否还要使用这份输入数据。",
                    hint_level_2="没有变量时，数据很难复用。",
                    hint_level_3="变量就像给数据贴标签，便于后续处理。",
                ),
                QuestionStep(
                    knowledge_point_id=kp.id,
                    step_no=2,
                    question_text="print(name) 和 print('name') 有什么区别？",
                    hint_level_1="一个是变量值，一个是字符串字面量。",
                    hint_level_2="带引号会原样输出文字。",
                    hint_level_3="不带引号时 Python 会查变量。",
                ),
            ]
        )
        db.commit()


def seed_model_provider(db: Session) -> None:
    if not db.query(ModelProvider).filter(ModelProvider.provider_name == "mock").first():
        db.add(
            ModelProvider(
                provider_name="mock",
                model_name="mock-chat",
                base_url="",
                api_key="",
                timeout_sec=30,
                retry_times=1,
                temperature="0.3",
                max_tokens=512,
                enabled=True,
                is_default=True,
            )
        )
    if not db.query(ModelProvider).filter(ModelProvider.provider_name == "openai_compatible").first():
        db.add(
            ModelProvider(
                provider_name="openai_compatible",
                model_name="gpt-4o-mini",
                base_url="https://api.openai.com/v1",
                api_key="",
                timeout_sec=30,
                retry_times=1,
                temperature="0.3",
                max_tokens=512,
                enabled=False,
                is_default=False,
            )
        )
    db.commit()


def seed_system_settings(db: Session) -> None:
    defaults = {
        "max_upload_mb": "20",
        "allowed_extensions": ".txt,.md,.pdf,.docx",
        "classroom_safety_level": "strict",
        "default_temperature": "0.3",
        "default_max_tokens": "512",
        "default_timeout_sec": "30",
    }
    for key, value in defaults.items():
        if not db.query(SystemConfig).filter(SystemConfig.key == key).first():
            db.add(SystemConfig(key=key, value=value))
    db.commit()


def main() -> None:
    info = get_database_debug_info()
    print(f"[seed] configured DATABASE_URL: {info['configured_url']}")
    print(f"[seed] resolved DATABASE_URL:   {info['resolved_url']}")
    if info["sqlite_path"]:
        print(f"[seed] sqlite file path:        {info['sqlite_path']}")

    db = SessionLocal()
    try:
        seed_users(db)
        seed_course_content(db)
        seed_model_provider(db)
        seed_system_settings(db)
        print("[seed] seed done")
    finally:
        db.close()


if __name__ == "__main__":
    main()
