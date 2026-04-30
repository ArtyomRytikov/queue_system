import os

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_db
from models import User, UserRole


def get_secret_key() -> str:
    try:
        from config import Config  # type: ignore

        legacy_key = getattr(Config, "SECRET_KEY", None)
    except Exception:
        legacy_key = None
    return os.getenv("SECRET_KEY") or legacy_key or "queue-system-secret"


def install_session_middleware(app) -> None:
    app.add_middleware(
        SessionMiddleware,
        secret_key=get_secret_key(),
        max_age=60 * 60 * 24,
        same_site="lax",
        https_only=False,
    )


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Нужна авторизация.")

    user = db.get(User, user_id)
    if not user or not user.is_active:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Сессия недействительна.")
    return user


def require_role(*roles: UserRole):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав.")
        return user

    return dependency
