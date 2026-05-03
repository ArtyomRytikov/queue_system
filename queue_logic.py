from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from models import Appointment, AppointmentStatus, AvailabilityRule, Service, Window


ACTIVE_APPOINTMENT_STATUSES = (
    AppointmentStatus.BOOKED,
    AppointmentStatus.CHECKED_IN,
    AppointmentStatus.CALLED,
)


def start_of_week(reference: date | None = None, week_offset: int = 0) -> date:
    current = reference or datetime.now().date()
    monday = current - timedelta(days=current.weekday())
    return monday + timedelta(weeks=week_offset)


def booking_code_for_today(db: Session) -> str:
    today = datetime.now().strftime("%Y%m%d")
    prefix = f"Q-{today}-"
    latest = db.scalar(
        select(Appointment.booking_code)
        .where(Appointment.booking_code.like(f"{prefix}%"))
        .order_by(Appointment.id.desc())
        .limit(1)
    )
    if not latest:
        return f"{prefix}001"
    number = int(latest.rsplit("-", 1)[-1]) + 1
    return f"{prefix}{number:03d}"


def overlaps(start: datetime, end: datetime, other_start: datetime, other_end: datetime) -> bool:
    return start < other_end and end > other_start


def get_day_rules(db: Session, target_day: date) -> list[AvailabilityRule]:
    return list(
        db.scalars(
            select(AvailabilityRule)
            .join(AvailabilityRule.window)
            .where(
                AvailabilityRule.weekday == target_day.weekday(),
                AvailabilityRule.is_active.is_(True),
                Window.is_active.is_(True),
            )
            .options(joinedload(AvailabilityRule.window))
            .order_by(AvailabilityRule.start_time, AvailabilityRule.window_id)
        )
    )


def get_day_appointments(db: Session, target_day: date) -> list[Appointment]:
    start_dt = datetime.combine(target_day, time.min)
    end_dt = datetime.combine(target_day, time.max)
    return list(
        db.scalars(
            select(Appointment)
            .where(
                Appointment.scheduled_start >= start_dt,
                Appointment.scheduled_start <= end_dt,
                Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            )
        )
    )


def slot_is_available(
    appointments: list[Appointment],
    window_id: int,
    start_dt: datetime,
    end_dt: datetime,
) -> bool:
    for appointment in appointments:
        if appointment.window_id != window_id:
            continue
        if overlaps(start_dt, end_dt, appointment.scheduled_start, appointment.scheduled_end):
            return False
    return True


def build_week_availability(db: Session, service: Service, week_start: date) -> list[dict]:
    week: list[dict] = []
    for day_offset in range(7):
        current_day = week_start + timedelta(days=day_offset)
        rules = get_day_rules(db, current_day)
        appointments = get_day_appointments(db, current_day)
        slots: list[dict] = []
        duration = timedelta(minutes=service.duration_minutes)

        for rule in rules:
            slot_start = datetime.combine(current_day, rule.start_time)
            rule_end = datetime.combine(current_day, rule.end_time)
            step = timedelta(minutes=rule.step_minutes)

            while slot_start + duration <= rule_end:
                slot_end = slot_start + duration
                if slot_start > datetime.now() and slot_is_available(appointments, rule.window_id, slot_start, slot_end):
                    slots.append(
                        {
                            "start": slot_start,
                            "end": slot_end,
                            "window_id": rule.window_id,
                            "window_name": rule.window.name,
                        }
                    )
                slot_start += step

        week.append(
            {
                "date": current_day,
                "weekday": current_day.weekday(),
                "label": current_day.strftime("%d.%m"),
                "slots": sorted(slots, key=lambda item: (item["start"], item["window_name"])),
            }
        )
    return week


def ensure_slot_available(
    db: Session,
    service: Service,
    window_id: int,
    scheduled_start: datetime,
) -> tuple[datetime, datetime]:
    scheduled_end = scheduled_start + timedelta(minutes=service.duration_minutes)
    target_day = scheduled_start.date()
    rules = get_day_rules(db, target_day)
    matching_rule = next(
        (
            rule
            for rule in rules
            if rule.window_id == window_id
            and datetime.combine(target_day, rule.start_time) <= scheduled_start
            and scheduled_end <= datetime.combine(target_day, rule.end_time)
        ),
        None,
    )
    if not matching_rule:
        raise ValueError("Для выбранного окна нет рабочего слота в это время.")

    appointments = get_day_appointments(db, target_day)
    if not slot_is_available(appointments, window_id, scheduled_start, scheduled_end):
        raise ValueError("Этот слот уже занят. Обновите календарь и выберите другой.")

    return scheduled_start, scheduled_end


def get_student_appointments(db: Session, user_id: int) -> list[Appointment]:
    return list(
        db.scalars(
            select(Appointment)
            .where(Appointment.user_id == user_id)
            .options(
                joinedload(Appointment.service),
                joinedload(Appointment.window),
            )
            .order_by(Appointment.scheduled_start.desc())
        )
    )


def get_operator_queue(db: Session, window_id: int, target_day: date | None = None) -> dict:
    current_day = target_day or datetime.now().date()
    start_dt = datetime.combine(current_day, time.min)
    end_dt = datetime.combine(current_day, time.max)

    appointments = list(
        db.scalars(
            select(Appointment)
            .where(
                Appointment.window_id == window_id,
                Appointment.scheduled_start >= start_dt,
                Appointment.scheduled_start <= end_dt,
                Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            )
            .options(
                joinedload(Appointment.student),
                joinedload(Appointment.service),
                joinedload(Appointment.window),
            )
            .order_by(
                Appointment.status == AppointmentStatus.CALLED,
                Appointment.scheduled_start,
            )
        )
    )

    current = next((item for item in appointments if item.status == AppointmentStatus.CALLED), None)
    waiting = [item for item in appointments if item.status != AppointmentStatus.CALLED]
    waiting.sort(
        key=lambda item: (
            0 if item.status == AppointmentStatus.CHECKED_IN else 1,
            item.scheduled_start,
        )
    )

    return {"current": current, "waiting": waiting}


def pick_next_appointment(db: Session, window_id: int) -> Appointment | None:
    queue = get_operator_queue(db, window_id)
    if queue["current"] is not None:
        raise ValueError("Сначала завершите или отметьте текущий вызов в этом окне.")

    waiting = queue["waiting"]
    if not waiting:
        return None

    now = datetime.now()
    eligible = [
        item
        for item in waiting
        if item.status == AppointmentStatus.CHECKED_IN or item.scheduled_start <= now + timedelta(minutes=15)
    ]
    if not eligible:
        raise ValueError("Пока еще рано вызывать следующую запись для этого окна.")

    next_item = eligible[0]
    next_item.status = AppointmentStatus.CALLED
    next_item.called_at = datetime.now()
    return next_item


def get_public_board(db: Session) -> dict:
    today = datetime.now().date()
    start_dt = datetime.combine(today, time.min)
    end_dt = datetime.combine(today, time.max)

    total = db.scalar(
        select(func.count(Appointment.id)).where(
            Appointment.scheduled_start >= start_dt,
            Appointment.scheduled_start <= end_dt,
        )
    ) or 0
    in_progress = db.scalar(
        select(func.count(Appointment.id)).where(
            Appointment.scheduled_start >= start_dt,
            Appointment.scheduled_start <= end_dt,
            Appointment.status == AppointmentStatus.CALLED,
        )
    ) or 0
    completed = db.scalar(
        select(func.count(Appointment.id)).where(
            Appointment.scheduled_start >= start_dt,
            Appointment.scheduled_start <= end_dt,
            Appointment.status == AppointmentStatus.COMPLETED,
        )
    ) or 0

    windows = list(
        db.scalars(
            select(Window)
            .where(Window.is_active.is_(True))
            .order_by(Window.name)
        )
    )

    window_items: list[dict] = []
    for window in windows:
        queue = get_operator_queue(db, window.id)
        current = queue["current"]
        window_items.append(
            {
                "id": window.id,
                "name": window.name,
                "location": window.location,
                "current": None
                if not current
                else {
                    "booking_code": current.booking_code,
                    "student_name": current.student.full_name,
                    "service_name": current.service.name,
                    "scheduled_start": current.scheduled_start.isoformat(),
                },
                "next": [
                    {
                        "booking_code": item.booking_code,
                        "student_name": item.student.full_name,
                        "service_name": item.service.name,
                        "scheduled_start": item.scheduled_start.isoformat(),
                    }
                    for item in queue["waiting"][:3]
                ],
            }
        )

    upcoming = list(
        db.scalars(
            select(Appointment)
            .where(
                Appointment.scheduled_start >= datetime.now(),
                Appointment.status.in_((AppointmentStatus.BOOKED, AppointmentStatus.CHECKED_IN)),
            )
            .options(
                joinedload(Appointment.service),
                joinedload(Appointment.window),
            )
            .order_by(Appointment.scheduled_start)
            .limit(8)
        )
    )

    return {
        "today_total": total,
        "in_progress": in_progress,
        "completed": completed,
        "windows": window_items,
        "upcoming": [
            {
                "booking_code": item.booking_code,
                "service_name": item.service.name,
                "window_name": item.window.name,
                "scheduled_start": item.scheduled_start.isoformat(),
            }
            for item in upcoming
        ],
    }
