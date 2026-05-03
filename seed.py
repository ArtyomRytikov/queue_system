from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import hash_password
from models import AvailabilityRule, Service, User, UserRole, Window


DEFAULT_SERVICES = [
    {
        "name": "Справка об обучении",
        "description": "Выдача справок, выписок и подтверждений для студентов.",
        "duration_minutes": 20,
        "color": "#1f7a8c",
    },
    {
        "name": "Академический отпуск",
        "description": "Оформление заявлений и проверка документов по академическому отпуску.",
        "duration_minutes": 30,
        "color": "#bf4342",
    },
    {
        "name": "Пересдача экзамена",
        "description": "Согласование пересдачи и подготовка документов по учебным задолженностям.",
        "duration_minutes": 25,
        "color": "#4d7c0f",
    },
    {
        "name": "Консультация",
        "description": "Личная консультация по учебному процессу и административным вопросам.",
        "duration_minutes": 40,
        "color": "#7c3aed",
    },
]


def seed_data(db: Session) -> None:
    if not db.scalar(select(Service.id).limit(1)):
        for payload in DEFAULT_SERVICES:
            db.add(Service(**payload))

    if not db.scalar(select(Window.id).limit(1)):
        db.add_all(
            [
                Window(name="Окно 1", location="Деканат, кабинет 201"),
                Window(name="Окно 2", location="Деканат, кабинет 202"),
                Window(name="Окно 3", location="Деканат, кабинет 203"),
            ]
        )
        db.flush()

    if not db.scalar(select(User.id).where(User.role == UserRole.ADMIN).limit(1)):
        db.add(
            User(
                username="admin",
                full_name="Главный администратор",
                email="admin@queue.local",
                password_hash=hash_password("admin12345"),
                role=UserRole.ADMIN,
            )
        )

    if not db.scalar(select(User.id).where(User.role == UserRole.OPERATOR).limit(1)):
        db.add(
            User(
                username="operator",
                full_name="Оператор деканата",
                email="operator@queue.local",
                password_hash=hash_password("operator12345"),
                role=UserRole.OPERATOR,
            )
        )

    db.flush()
    windows = list(db.scalars(select(Window).order_by(Window.id)))
    if windows and not db.scalar(select(AvailabilityRule.id).limit(1)):
        for window in windows:
            for weekday in range(0, 5):
                db.add(
                    AvailabilityRule(
                        window_id=window.id,
                        weekday=weekday,
                        start_time=time(9, 0),
                        end_time=time(17, 0),
                        step_minutes=30,
                    )
                )

    db.commit()
