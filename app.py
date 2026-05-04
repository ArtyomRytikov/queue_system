from datetime import datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from auth import (
    get_current_user,
    hash_password,
    install_session_middleware,
    require_role,
    verify_password,
)
from database import Base, SessionLocal, engine, get_db
from migration import migrate_legacy_data, migrate_legacy_schema
from models import Appointment, AppointmentStatus, AvailabilityRule, Service, User, UserRole, Window
from queue_logic import (
    ACTIVE_APPOINTMENT_STATUSES,
    booking_code_for_today,
    build_week_availability,
    ensure_slot_available,
    get_operator_queue,
    get_public_board,
    get_student_appointments,
    pick_next_appointment,
    start_of_week,
)
from schemas import (
    AppointmentActionPayload,
    AvailabilityRulePayload,
    BookingPayload,
    LoginPayload,
    RegisterPayload,
    ServicePayload,
    WindowPayload,
)
from seed import seed_data


app = FastAPI(
    title="Queue System",
    description="Современная система онлайн-записи и электронной очереди для деканата.",
    version="2.0.0",
)
install_session_middleware(app)
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
STATIC_VERSION = "2026-04-08-03"


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role.value,
    }


def build_username(db: Session, email: str) -> str:
    base = email.split("@", 1)[0].strip().lower() or "user"
    base = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in base)[:80] or "user"
    candidate = base
    suffix = 1
    while db.scalar(select(User.id).where(User.username == candidate)):
        suffix += 1
        candidate = f"{base[:75]}_{suffix}"
    return candidate


def serialize_service(service: Service) -> dict:
    return {
        "id": service.id,
        "name": service.name,
        "description": service.description,
        "duration_minutes": service.duration_minutes,
        "color": service.color,
        "is_active": service.is_active,
    }


def serialize_window(window: Window) -> dict:
    return {
        "id": window.id,
        "name": window.name,
        "location": window.location,
        "is_active": window.is_active,
    }


def serialize_rule(rule: AvailabilityRule) -> dict:
    return {
        "id": rule.id,
        "window_id": rule.window_id,
        "window_name": rule.window.name if rule.window else "",
        "weekday": rule.weekday,
        "start_time": rule.start_time.strftime("%H:%M"),
        "end_time": rule.end_time.strftime("%H:%M"),
        "step_minutes": rule.step_minutes,
        "is_active": rule.is_active,
    }


def serialize_appointment(appointment: Appointment, include_student: bool = False) -> dict:
    payload = {
        "id": appointment.id,
        "booking_code": appointment.booking_code,
        "status": appointment.status.value,
        "scheduled_start": appointment.scheduled_start.isoformat(),
        "scheduled_end": appointment.scheduled_end.isoformat(),
        "notes": appointment.notes,
        "created_at": appointment.created_at.isoformat(),
        "checked_in_at": appointment.checked_in_at.isoformat() if appointment.checked_in_at else None,
        "called_at": appointment.called_at.isoformat() if appointment.called_at else None,
        "completed_at": appointment.completed_at.isoformat() if appointment.completed_at else None,
        "service": serialize_service(appointment.service),
        "window": serialize_window(appointment.window),
    }
    if include_student:
        payload["student"] = {
            "id": appointment.student.id,
            "full_name": appointment.student.full_name,
            "email": appointment.student.email,
        }
    return payload


def require_owned_appointment(
    db: Session,
    appointment_id: int,
    user_id: int,
) -> Appointment:
    appointment = db.scalar(
        select(Appointment)
        .where(Appointment.id == appointment_id, Appointment.user_id == user_id)
        .options(
            joinedload(Appointment.service),
            joinedload(Appointment.window),
        )
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена.")
    return appointment


def require_operator_appointment(db: Session, appointment_id: int) -> Appointment:
    appointment = db.scalar(
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .options(
            joinedload(Appointment.student),
            joinedload(Appointment.service),
            joinedload(Appointment.window),
        )
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена.")
    return appointment


@app.on_event("startup")
def on_startup() -> None:
    migrate_legacy_schema(engine)
    Base.metadata.create_all(bind=engine)
    migrate_legacy_data(engine)
    with SessionLocal() as db:
        seed_data(db)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "static_version": STATIC_VERSION},
    )


@app.get("/api/services")
def list_services(db: Session = Depends(get_db)) -> dict:
    services = list(
        db.scalars(
            select(Service).where(Service.is_active.is_(True)).order_by(Service.name)
        )
    )
    return {"services": [serialize_service(service) for service in services]}


@app.get("/api/board")
def public_board(db: Session = Depends(get_db)) -> dict:
    return get_public_board(db)


@app.post("/api/auth/register")
def register(
    payload: RegisterPayload,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    if payload.password != payload.password_repeat:
        raise HTTPException(status_code=400, detail="Пароли не совпадают.")

    email = payload.email.lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с такой почтой уже существует.")

    user = User(
        username=build_username(db, email),
        full_name=payload.full_name,
        email=email,
        password_hash=hash_password(payload.password),
        role=UserRole.STUDENT,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    request.session["user_id"] = user.id
    return {"message": "Регистрация прошла успешно.", "user": serialize_user(user)}


@app.post("/api/auth/login")
def login(
    payload: LoginPayload,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверная почта или пароль.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Учетная запись отключена.")

    request.session["user_id"] = user.id
    return {"message": "Вход выполнен.", "user": serialize_user(user)}


@app.post("/api/auth/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"message": "Вы вышли из системы."}


@app.get("/api/auth/me")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return {"user": serialize_user(current_user)}


@app.get("/api/student/availability")
def student_availability(
    service_id: int,
    week_offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT, UserRole.ADMIN)),
) -> dict:
    if week_offset < 0 or week_offset > 8:
        raise HTTPException(status_code=400, detail="Можно смотреть расписание только на 9 недель вперед.")

    service = db.get(Service, service_id)
    if not service or not service.is_active:
        raise HTTPException(status_code=404, detail="Услуга не найдена.")

    week_start = start_of_week(week_offset=week_offset)
    days = build_week_availability(db, service, week_start)
    return {
        "service": serialize_service(service),
        "week_start": week_start.isoformat(),
        "days": [
            {
                "date": day["date"].isoformat(),
                "weekday": day["weekday"],
                "label": day["label"],
                "slots": [
                    {
                        "start": slot["start"].isoformat(),
                        "end": slot["end"].isoformat(),
                        "window_id": slot["window_id"],
                        "window_name": slot["window_name"],
                    }
                    for slot in day["slots"]
                ],
            }
            for day in days
        ],
    }


@app.get("/api/student/appointments")
def student_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT, UserRole.ADMIN)),
) -> dict:
    appointments = get_student_appointments(db, current_user.id)
    return {"appointments": [serialize_appointment(item) for item in appointments]}


@app.post("/api/student/appointments")
def create_appointment(
    payload: BookingPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT, UserRole.ADMIN)),
) -> dict:
    service = db.get(Service, payload.service_id)
    if not service or not service.is_active:
        raise HTTPException(status_code=404, detail="Услуга недоступна.")

    window = db.get(Window, payload.window_id)
    if not window or not window.is_active:
        raise HTTPException(status_code=404, detail="Окно не найдено.")

    if payload.scheduled_start <= datetime.now():
        raise HTTPException(status_code=400, detail="Нельзя записаться в прошедшее время.")

    if payload.scheduled_start > datetime.now() + timedelta(weeks=8):
        raise HTTPException(status_code=400, detail="Запись доступна максимум на 8 недель вперед.")

    try:
        scheduled_start, scheduled_end = ensure_slot_available(
            db,
            service,
            payload.window_id,
            payload.scheduled_start,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    user_conflict = db.scalar(
        select(Appointment.id).where(
            Appointment.user_id == current_user.id,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.scheduled_start < scheduled_end,
            Appointment.scheduled_end > scheduled_start,
        )
    )
    if user_conflict:
        raise HTTPException(
            status_code=400,
            detail="У вас уже есть другая активная запись на это время.",
        )

    appointment = Appointment(
        booking_code=booking_code_for_today(db),
        user_id=current_user.id,
        service_id=service.id,
        window_id=window.id,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        notes=payload.notes.strip(),
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    appointment = require_owned_appointment(db, appointment.id, current_user.id)
    return {
        "message": "Запись создана.",
        "appointment": serialize_appointment(appointment),
    }


@app.post("/api/student/appointments/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: int,
    payload: AppointmentActionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT, UserRole.ADMIN)),
) -> dict:
    appointment = require_owned_appointment(db, appointment_id, current_user.id)
    if appointment.status not in (AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN):
        raise HTTPException(status_code=400, detail="Эту запись уже нельзя отменить.")

    appointment.status = AppointmentStatus.CANCELED
    if payload.note.strip():
        appointment.notes = payload.note.strip()
    db.commit()
    db.refresh(appointment)
    return {"message": "Запись отменена.", "appointment": serialize_appointment(appointment)}


@app.post("/api/student/appointments/{appointment_id}/check-in")
def check_in_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT, UserRole.ADMIN)),
) -> dict:
    appointment = require_owned_appointment(db, appointment_id, current_user.id)
    if appointment.status != AppointmentStatus.BOOKED:
        raise HTTPException(status_code=400, detail="Запись уже отмечена или завершена.")

    now = datetime.now()
    if appointment.scheduled_start.date() != now.date():
        raise HTTPException(status_code=400, detail="Подтверждение прихода доступно только в день записи.")
    if appointment.scheduled_start - now > timedelta(hours=2):
        raise HTTPException(status_code=400, detail="Слишком рано для подтверждения прихода.")

    appointment.status = AppointmentStatus.CHECKED_IN
    appointment.checked_in_at = datetime.now()
    db.commit()
    db.refresh(appointment)
    return {"message": "Вы отмечены в очереди.", "appointment": serialize_appointment(appointment)}


@app.get("/api/operator/windows")
def operator_windows(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
) -> dict:
    windows = list(db.scalars(select(Window).where(Window.is_active.is_(True)).order_by(Window.name)))
    return {"windows": [serialize_window(window) for window in windows]}


@app.get("/api/operator/dashboard")
def operator_dashboard(
    window_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
) -> dict:
    window = db.get(Window, window_id)
    if not window or not window.is_active:
        raise HTTPException(status_code=404, detail="Окно не найдено.")

    queue = get_operator_queue(db, window_id)
    return {
        "window": serialize_window(window),
        "current": serialize_appointment(queue["current"], include_student=True) if queue["current"] else None,
        "waiting": [serialize_appointment(item, include_student=True) for item in queue["waiting"]],
    }


@app.post("/api/operator/windows/{window_id}/next")
def operator_next(
    window_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
) -> dict:
    window = db.get(Window, window_id)
    if not window or not window.is_active:
        raise HTTPException(status_code=404, detail="Окно не найдено.")

    try:
        appointment = pick_next_appointment(db, window_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    if not appointment:
        raise HTTPException(status_code=404, detail="В очереди пока нет записей.")

    appointment.operator_id = current_user.id
    db.commit()
    appointment = require_operator_appointment(db, appointment.id)
    return {"message": "Следующий студент вызван.", "appointment": serialize_appointment(appointment, include_student=True)}


@app.post("/api/operator/appointments/{appointment_id}/complete")
def operator_complete(
    appointment_id: int,
    payload: AppointmentActionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
) -> dict:
    appointment = require_operator_appointment(db, appointment_id)
    if appointment.status != AppointmentStatus.CALLED:
        raise HTTPException(status_code=400, detail="Сначала нужно вызвать запись.")

    appointment.status = AppointmentStatus.COMPLETED
    appointment.completed_at = datetime.now()
    appointment.operator_id = current_user.id
    if payload.note.strip():
        appointment.notes = payload.note.strip()
    db.commit()
    appointment = require_operator_appointment(db, appointment.id)
    return {"message": "Прием завершен.", "appointment": serialize_appointment(appointment, include_student=True)}


@app.post("/api/operator/appointments/{appointment_id}/no-show")
def operator_no_show(
    appointment_id: int,
    payload: AppointmentActionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
) -> dict:
    appointment = require_operator_appointment(db, appointment_id)
    if appointment.status not in (AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN, AppointmentStatus.CALLED):
        raise HTTPException(status_code=400, detail="Неявку можно отметить только для активной записи.")

    appointment.status = AppointmentStatus.NO_SHOW
    appointment.completed_at = datetime.now()
    appointment.operator_id = current_user.id
    if payload.note.strip():
        appointment.notes = payload.note.strip()
    db.commit()
    appointment = require_operator_appointment(db, appointment.id)
    return {"message": "Неявка отмечена.", "appointment": serialize_appointment(appointment, include_student=True)}


@app.post("/api/operator/appointments/{appointment_id}/check-in")
def operator_mark_arrival(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.OPERATOR, UserRole.ADMIN)),
) -> dict:
    appointment = require_operator_appointment(db, appointment_id)
    if appointment.status != AppointmentStatus.BOOKED:
        raise HTTPException(status_code=400, detail="Эту запись уже нельзя отметить как пришедшую.")

    appointment.status = AppointmentStatus.CHECKED_IN
    appointment.checked_in_at = datetime.now()
    appointment.operator_id = current_user.id
    db.commit()
    appointment = require_operator_appointment(db, appointment.id)
    return {"message": "Студент отмечен как пришедший.", "appointment": serialize_appointment(appointment, include_student=True)}


@app.get("/api/admin/overview")
def admin_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> dict:
    services = list(db.scalars(select(Service).order_by(Service.name)))
    windows = list(db.scalars(select(Window).order_by(Window.name)))
    rules = list(
        db.scalars(
            select(AvailabilityRule)
            .options(joinedload(AvailabilityRule.window))
            .order_by(AvailabilityRule.weekday, AvailabilityRule.start_time, AvailabilityRule.window_id)
        )
    )
    users_total = db.scalar(select(func.count(User.id))) or 0
    board = get_public_board(db)
    return {
        "stats": {"users_total": users_total, **board},
        "services": [serialize_service(service) for service in services],
        "windows": [serialize_window(window) for window in windows],
        "rules": [serialize_rule(rule) for rule in rules],
    }


@app.post("/api/admin/services")
def admin_create_service(
    payload: ServicePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> dict:
    exists = db.scalar(select(Service.id).where(Service.name == payload.name.strip()))
    if exists:
        raise HTTPException(status_code=400, detail="Услуга с таким названием уже существует.")

    service = Service(
        name=payload.name.strip(),
        description=payload.description.strip(),
        duration_minutes=payload.duration_minutes,
        color=payload.color.strip(),
        is_active=payload.is_active,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return {"message": "Услуга создана.", "service": serialize_service(service)}


@app.put("/api/admin/services/{service_id}")
def admin_update_service(
    service_id: int,
    payload: ServicePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> dict:
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Услуга не найдена.")

    duplicate = db.scalar(
        select(Service.id).where(Service.name == payload.name.strip(), Service.id != service_id)
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Услуга с таким названием уже существует.")

    service.name = payload.name.strip()
    service.description = payload.description.strip()
    service.duration_minutes = payload.duration_minutes
    service.color = payload.color.strip()
    service.is_active = payload.is_active
    db.commit()
    db.refresh(service)
    return {"message": "Услуга обновлена.", "service": serialize_service(service)}


@app.post("/api/admin/windows")
def admin_create_window(
    payload: WindowPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> dict:
    exists = db.scalar(select(Window.id).where(Window.name == payload.name.strip()))
    if exists:
        raise HTTPException(status_code=400, detail="Окно с таким названием уже существует.")

    window = Window(
        name=payload.name.strip(),
        location=payload.location.strip(),
        is_active=payload.is_active,
    )
    db.add(window)
    db.commit()
    db.refresh(window)
    return {"message": "Окно создано.", "window": serialize_window(window)}


@app.put("/api/admin/windows/{window_id}")
def admin_update_window(
    window_id: int,
    payload: WindowPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> dict:
    window = db.get(Window, window_id)
    if not window:
        raise HTTPException(status_code=404, detail="Окно не найдено.")

    duplicate = db.scalar(select(Window.id).where(Window.name == payload.name.strip(), Window.id != window_id))
    if duplicate:
        raise HTTPException(status_code=400, detail="Окно с таким названием уже существует.")

    window.name = payload.name.strip()
    window.location = payload.location.strip()
    window.is_active = payload.is_active
    db.commit()
    db.refresh(window)
    return {"message": "Окно обновлено.", "window": serialize_window(window)}


@app.post("/api/admin/rules")
def admin_create_rule(
    payload: AvailabilityRulePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> dict:
    window = db.get(Window, payload.window_id)
    if not window:
        raise HTTPException(status_code=404, detail="Окно не найдено.")
    if payload.start_time >= payload.end_time:
        raise HTTPException(status_code=400, detail="Время окончания должно быть позже времени начала.")

    rule = AvailabilityRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    rule = db.scalar(
        select(AvailabilityRule)
        .where(AvailabilityRule.id == rule.id)
        .options(joinedload(AvailabilityRule.window))
    )
    return {"message": "Правило расписания создано.", "rule": serialize_rule(rule)}


@app.put("/api/admin/rules/{rule_id}")
def admin_update_rule(
    rule_id: int,
    payload: AvailabilityRulePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> dict:
    rule = db.get(AvailabilityRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено.")
    if payload.start_time >= payload.end_time:
        raise HTTPException(status_code=400, detail="Время окончания должно быть позже времени начала.")

    window = db.get(Window, payload.window_id)
    if not window:
        raise HTTPException(status_code=404, detail="Окно не найдено.")

    for field, value in payload.model_dump().items():
        setattr(rule, field, value)
    db.commit()
    rule = db.scalar(
        select(AvailabilityRule)
        .where(AvailabilityRule.id == rule.id)
        .options(joinedload(AvailabilityRule.window))
    )
    return {"message": "Правило расписания обновлено.", "rule": serialize_rule(rule)}
