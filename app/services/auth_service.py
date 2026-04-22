from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import User


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
