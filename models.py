import enum
from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def local_now() -> datetime:
    return datetime.now()


class UserRole(str, enum.Enum):
    STUDENT = "STUDENT"
    OPERATOR = "OPERATOR"
    ADMIN = "ADMIN"


class AppointmentStatus(str, enum.Enum):
    BOOKED = "BOOKED"
    CHECKED_IN = "CHECKED_IN"
    CALLED = "CALLED"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"
    NO_SHOW = "NO_SHOW"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False),
        default=UserRole.STUDENT,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)

    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="student",
        foreign_keys="Appointment.user_id",
        cascade="all, delete-orphan",
    )
    operated_appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="operator",
        foreign_keys="Appointment.operator_id",
    )


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    color: Mapped[str] = mapped_column(String(30), default="#2f6fed", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="service")


class Window(Base):
    __tablename__ = "windows"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    location: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)

    rules: Mapped[list["AvailabilityRule"]] = relationship(
        back_populates="window",
        cascade="all, delete-orphan",
    )
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="window")


class AvailabilityRule(Base):
    __tablename__ = "availability_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    window_id: Mapped[int] = mapped_column(ForeignKey("windows.id"), nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(nullable=False)
    end_time: Mapped[time] = mapped_column(nullable=False)
    step_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)

    window: Mapped["Window"] = relationship(back_populates="rules")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=False)
    window_id: Mapped[int] = mapped_column(ForeignKey("windows.id"), nullable=False)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, native_enum=False),
        default=AppointmentStatus.BOOKED,
        nullable=False,
    )
    scheduled_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=local_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=local_now,
        onupdate=local_now,
        nullable=False,
    )
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime)
    called_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    student: Mapped["User"] = relationship(back_populates="appointments", foreign_keys=[user_id])
    operator: Mapped["User"] = relationship(back_populates="operated_appointments", foreign_keys=[operator_id])
    service: Mapped["Service"] = relationship(back_populates="appointments")
    window: Mapped["Window"] = relationship(back_populates="appointments")


Index("ix_appointments_window_start", Appointment.window_id, Appointment.scheduled_start)
Index("ix_appointments_status_start", Appointment.status, Appointment.scheduled_start)
