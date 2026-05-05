"""Pydantic models for Personio API V2 data."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PersonioProjectRef(BaseModel):
    """Lightweight reference to another project (e.g. parent_project).

    The V2 API embeds related entities as `{"id": "..."}` objects.
    """

    model_config = ConfigDict(extra="allow")

    id: str


class PersonioProject(BaseModel):
    """Project from the Personio V2 API.

    IDs are UUID strings (not numeric like V1). Computed fields like
    ``tracked_minutes`` only appear when requested via ``include[]`` and are
    accepted via ``extra="allow"``.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    status: Literal["ACTIVE", "ARCHIVED"]
    assigned_to_all: bool = False
    parent_project: PersonioProjectRef | None = None
    project_code: str | None = None
    description: str | None = None
    cost_center: str | None = None
    start: date | None = None
    end: date | None = None
    billable: bool | None = None
    client_name: str | None = None
    project_type: str | None = None


class PersonioPersonRef(BaseModel):
    """Lightweight reference to a person/employee."""

    model_config = ConfigDict(extra="allow")

    id: str


class PersonioDateTimeRef(BaseModel):
    """V2 wraps datetimes as ``{"date_time": "..."}`` objects."""

    model_config = ConfigDict(extra="allow")

    date_time: datetime = Field(alias="date_time")


class PersonioAttendancePeriod(BaseModel):
    """Attendance period from the Personio V2 API.

    Replaces the V1 ``/v1/company/attendances`` resource. IDs are UUID strings.
    A period of ``type=BREAK`` cannot be linked to a project.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    person: PersonioPersonRef
    type: Literal["WORK", "BREAK"]
    start: PersonioDateTimeRef
    end: PersonioDateTimeRef | None = None
    attribution_date: date | None = None
    status: Literal["PENDING", "CONFIRMED", "REJECTED"]
    project: PersonioProjectRef | None = None
    comment: str | None = None
