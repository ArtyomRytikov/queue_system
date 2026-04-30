from datetime import date, datetime, time

from pydantic import BaseModel, Field, field_validator

from models import AppointmentStatus, UserRole


class RegisterPayload(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    password_repeat: str = Field(min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Введите корректную почту.")
        return normalized


class LoginPayload(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_login_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("Введите корректную почту.")
        return normalized


class ServicePayload(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    description: str = Field(default="", max_length=1000)
    duration_minutes: int = Field(ge=10, le=180)
    color: str = Field(default="#2f6fed", pattern=r"^#[0-9a-fA-F]{6}$")
    is_active: bool = True


class WindowPayload(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    location: str = Field(default="", max_length=120)
    is_active: bool = True


class AvailabilityRulePayload(BaseModel):
    window_id: int
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    step_minutes: int = Field(ge=10, le=120)
    is_active: bool = True


class BookingPayload(BaseModel):
    service_id: int
    window_id: int
    scheduled_start: datetime
    notes: str = Field(default="", max_length=500)


class AppointmentActionPayload(BaseModel):
    note: str = Field(default="", max_length=500)


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    role: UserRole

    class Config:
        from_attributes = True


class ServiceResponse(BaseModel):
    id: int
    name: str
    description: str
    duration_minutes: int
    color: str
    is_active: bool

    class Config:
        from_attributes = True


class WindowResponse(BaseModel):
    id: int
    name: str
    location: str
    is_active: bool

    class Config:
        from_attributes = True


class RuleResponse(BaseModel):
    id: int
    window_id: int
    weekday: int
    start_time: time
    end_time: time
    step_minutes: int
    is_active: bool

    class Config:
        from_attributes = True


class SlotResponse(BaseModel):
    start: datetime
    end: datetime
    window_id: int
    window_name: str


class DayAvailabilityResponse(BaseModel):
    date: date
    weekday: int
    label: str
    slots: list[SlotResponse]


class AppointmentResponse(BaseModel):
    id: int
    booking_code: str
    status: AppointmentStatus
    scheduled_start: datetime
    scheduled_end: datetime
    notes: str
    created_at: datetime
    checked_in_at: datetime | None = None
    called_at: datetime | None = None
    completed_at: datetime | None = None
    service: ServiceResponse
    window: WindowResponse


class PublicBoardResponse(BaseModel):
    today_total: int
    in_progress: int
    completed: int
    windows: list[dict]
    upcoming: list[dict]
