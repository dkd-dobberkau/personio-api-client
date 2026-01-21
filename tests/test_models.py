"""Tests for Personio models."""

from datetime import date

from personio_api_client import (
    PersonioEmployee,
    PersonioTimeOff,
    PersonioTimeOffType,
    PersonioWorkSchedule,
)


class TestPersonioWorkSchedule:
    def test_hours_for_weekday(self):
        schedule = PersonioWorkSchedule(
            id=1,
            name="Full-time",
            monday="08:00",
            tuesday="08:00",
            wednesday="08:00",
            thursday="08:00",
            friday="06:00",
            saturday="00:00",
            sunday="00:00",
        )

        assert schedule.hours_for_weekday(0) == 8.0  # Monday
        assert schedule.hours_for_weekday(4) == 6.0  # Friday
        assert schedule.hours_for_weekday(5) == 0.0  # Saturday

    def test_hours_with_minutes(self):
        schedule = PersonioWorkSchedule(
            id=1,
            name="Part-time",
            monday="04:30",
            tuesday="04:30",
        )

        assert schedule.hours_for_weekday(0) == 4.5  # 4h 30m


class TestPersonioTimeOffType:
    def test_basic_creation(self):
        time_off_type = PersonioTimeOffType(
            id=1,
            name="Vacation",
            category="vacation",
        )

        assert time_off_type.id == 1
        assert time_off_type.name == "Vacation"
        assert time_off_type.category == "vacation"


class TestPersonioTimeOff:
    def test_employee_name_full(self):
        time_off = PersonioTimeOff(
            id=1,
            employee_id=100,
            employee_first_name="John",
            employee_last_name="Doe",
            time_off_type_id=1,
            time_off_type_name="Vacation",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
        )

        assert time_off.employee_name == "John Doe"

    def test_employee_name_fallback_email(self):
        time_off = PersonioTimeOff(
            id=1,
            employee_id=100,
            employee_email="john@example.com",
            time_off_type_id=1,
            time_off_type_name="Vacation",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
        )

        assert time_off.employee_name == "john@example.com"

    def test_employee_name_fallback_id(self):
        time_off = PersonioTimeOff(
            id=1,
            employee_id=100,
            time_off_type_id=1,
            time_off_type_name="Vacation",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
        )

        assert time_off.employee_name == "Employee 100"


class TestPersonioEmployee:
    def test_name_full(self):
        employee = PersonioEmployee(
            id=1,
            first_name="Jane",
            last_name="Smith",
        )

        assert employee.name == "Jane Smith"

    def test_name_fallback_email(self):
        employee = PersonioEmployee(
            id=1,
            email="jane@example.com",
        )

        assert employee.name == "jane@example.com"

    def test_name_fallback_id(self):
        employee = PersonioEmployee(id=1)

        assert employee.name == "Employee 1"

    def test_with_work_schedule(self):
        schedule = PersonioWorkSchedule(
            id=1,
            name="Full-time",
            monday="08:00",
        )

        employee = PersonioEmployee(
            id=1,
            first_name="Jane",
            last_name="Smith",
            work_schedule=schedule,
        )

        assert employee.work_schedule is not None
        assert employee.work_schedule.name == "Full-time"
