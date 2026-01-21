"""Pydantic models for Personio API data."""

from datetime import date

from pydantic import BaseModel


class PersonioWorkSchedule(BaseModel):
    """Work schedule from Personio."""

    id: int
    name: str
    valid_from: date | None = None
    monday: str = "00:00"  # Format: "HH:MM"
    tuesday: str = "00:00"
    wednesday: str = "00:00"
    thursday: str = "00:00"
    friday: str = "00:00"
    saturday: str = "00:00"
    sunday: str = "00:00"

    def hours_for_weekday(self, weekday: int) -> float:
        """
        Get scheduled hours for a weekday.

        Args:
            weekday: 0=Monday, 6=Sunday

        Returns:
            Hours as float (e.g., 8.5 for 8:30)
        """
        days = [
            self.monday,
            self.tuesday,
            self.wednesday,
            self.thursday,
            self.friday,
            self.saturday,
            self.sunday,
        ]
        time_str = days[weekday]
        if ":" in time_str:
            hours, minutes = time_str.split(":")
            return int(hours) + int(minutes) / 60
        return float(time_str) if time_str else 0.0


class PersonioTimeOffType(BaseModel):
    """Time-off type (e.g., vacation, sick leave)."""

    id: int
    name: str
    category: str | None = None  # e.g., "vacation", "sick_leave"


class PersonioTimeOff(BaseModel):
    """Time-off entry from Personio."""

    id: int
    employee_id: int
    employee_email: str | None = None
    employee_first_name: str | None = None
    employee_last_name: str | None = None
    time_off_type_id: int
    time_off_type_name: str
    start_date: date
    end_date: date
    days_count: float = 0.0
    half_day_start: bool = False
    half_day_end: bool = False
    status: str = "approved"  # approved, pending, rejected
    comment: str | None = None

    @property
    def employee_name(self) -> str:
        """Full name of the employee."""
        if self.employee_first_name and self.employee_last_name:
            return f"{self.employee_first_name} {self.employee_last_name}"
        return self.employee_email or f"Employee {self.employee_id}"


class PersonioEmployee(BaseModel):
    """Employee from Personio."""

    id: int
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    status: str | None = None  # active, inactive, onboarding
    department: str | None = None
    team: str | None = None
    position: str | None = None
    hire_date: date | None = None
    termination_date: date | None = None
    weekly_working_hours: float | None = None
    work_schedule: PersonioWorkSchedule | None = None

    @property
    def name(self) -> str:
        """Full name of the employee."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.email or f"Employee {self.id}"
