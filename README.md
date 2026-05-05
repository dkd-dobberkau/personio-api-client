# personio-api-client

Python client for the [Personio](https://www.personio.de/) REST API.

Supports both API versions:

- **`PersonioClient`** (V1) — Employees and Time-Offs (Abwesenheiten).
- **`PersonioV2Client`** (V2) — Attendance Periods and Projects.
  Use this if you depend on `/v1/company/attendances` or
  `/v1/company/attendances/projects`; Personio is shutting these V1
  endpoints down in 2026.

## Installation

```bash
pip install personio-api-client
```

Or with uv:

```bash
uv add personio-api-client
```

## Quick Start

```python
from datetime import date
from personio_api_client import PersonioClient

# Using environment variables (recommended)
# Set PERSONIO_CLIENT_ID and PERSONIO_CLIENT_SECRET

with PersonioClient() as client:
    # Get all active employees
    employees = client.get_employees()

    # Get time-offs for a date range
    time_offs = client.get_time_offs(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )

    # Get time-off types
    types = client.get_time_off_types()
```

## Configuration

### Environment Variables

```bash
export PERSONIO_CLIENT_ID="your-client-id"
export PERSONIO_CLIENT_SECRET="your-client-secret"
```

### Explicit Credentials

```python
client = PersonioClient(
    client_id="your-client-id",
    client_secret="your-client-secret",
)
```

### Options

```python
client = PersonioClient(
    client_id="...",
    client_secret="...",
    base_url="https://api.personio.de/v1",  # default
    timeout=30.0,  # seconds, default
)
```

## API Reference

### PersonioClient

#### `get_employees(active_only=True)`

Get all employees from Personio.

```python
employees = client.get_employees()
for emp in employees:
    print(f"{emp.name} - {emp.department}")
```

Returns: `list[PersonioEmployee]`

#### `get_time_offs(start_date=None, end_date=None, employee_ids=None)`

Get time-offs (vacation, sick leave, etc.).

```python
from datetime import date

time_offs = client.get_time_offs(
    start_date=date(2025, 1, 1),
    end_date=date(2025, 12, 31),
)

for t in time_offs:
    print(f"{t.employee_name}: {t.time_off_type_name} ({t.start_date} - {t.end_date})")
```

Returns: `list[PersonioTimeOff]`

#### `get_time_off_types()`

Get all time-off types.

```python
types = client.get_time_off_types()
for t in types:
    print(f"{t.name} ({t.category})")
```

Returns: `list[PersonioTimeOffType]`

## Models

### PersonioEmployee

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Employee ID |
| `email` | `str \| None` | Email address |
| `first_name` | `str \| None` | First name |
| `last_name` | `str \| None` | Last name |
| `status` | `str \| None` | active, inactive, onboarding |
| `department` | `str \| None` | Department name |
| `team` | `str \| None` | Team name |
| `position` | `str \| None` | Position title |
| `hire_date` | `date \| None` | Hire date |
| `termination_date` | `date \| None` | Termination date |
| `weekly_working_hours` | `float \| None` | Weekly hours |
| `work_schedule` | `PersonioWorkSchedule \| None` | Work schedule |

Property: `name` - Full name or fallback to email/ID

### PersonioTimeOff

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Time-off ID |
| `employee_id` | `int` | Employee ID |
| `employee_email` | `str \| None` | Employee email |
| `employee_first_name` | `str \| None` | Employee first name |
| `employee_last_name` | `str \| None` | Employee last name |
| `time_off_type_id` | `int` | Type ID |
| `time_off_type_name` | `str` | Type name |
| `start_date` | `date` | Start date |
| `end_date` | `date` | End date |
| `days_count` | `float` | Number of days |
| `half_day_start` | `bool` | Half day at start |
| `half_day_end` | `bool` | Half day at end |
| `status` | `str` | approved, pending, rejected |
| `comment` | `str \| None` | Comment |

Property: `employee_name` - Full name or fallback

### PersonioWorkSchedule

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Schedule ID |
| `name` | `str` | Schedule name |
| `valid_from` | `date \| None` | Valid from date |
| `monday` - `sunday` | `str` | Hours per day (HH:MM format) |

Method: `hours_for_weekday(weekday: int)` - Get hours for weekday (0=Monday)

## V2 API (Attendances and Projects)

`PersonioV2Client` targets `https://api.personio.de/v2`. It uses the OAuth 2.0
`client_credentials` flow and reads the same `PERSONIO_CLIENT_ID` /
`PERSONIO_CLIENT_SECRET` environment variables as the V1 client.

```python
from datetime import date, datetime, UTC
from personio_api_client import PersonioV2Client

with PersonioV2Client() as client:
    # List active projects (cursor pagination handled internally).
    projects = client.list_projects(status="ACTIVE")

    # Create a project.
    new_project = client.create_project(
        name="Phoenix",
        project_code="PHX-001",
        billable=True,
    )

    # List attendance periods for a date range.
    periods = client.list_attendance_periods(
        person_ids=["emp-uuid-1", "emp-uuid-2"],
        start_gte=datetime(2026, 5, 1, tzinfo=UTC),
        end_lte=datetime(2026, 5, 31, 23, 59, tzinfo=UTC),
        status="CONFIRMED",
    )

    # Create an attendance period (server may split it into multiple).
    created = client.create_attendance_period(
        person_id="emp-uuid-1",
        type="WORK",
        start=datetime(2026, 5, 4, 8, 0, tzinfo=UTC),
        end=datetime(2026, 5, 4, 16, 30, tzinfo=UTC),
        project_id=new_project.id,
        skip_approval=True,
    )
```

### V1 vs V2 — what changes

| Aspect | V1 | V2 |
|--------|----|----|
| Base URL | `https://api.personio.de/v1` | `https://api.personio.de/v2` |
| Auth | Custom `POST /v1/auth` | OAuth 2.0 `POST /v2/auth/token` (`grant_type=client_credentials`) |
| Resource name | `attendances` | `attendance-periods` |
| IDs | numeric | UUID strings |
| Pagination | `limit` + `offset` | cursor (`cursor` + `limit`) |
| Errors | `{success: false, error: {…}}` | RFC 7807 `application/problem+json` |
| Approval default | implicit skip | requires approval; opt out via `skip_approval=True` |
| Project status | `active: bool` | `status: "ACTIVE" \| "ARCHIVED"` |

### V2 methods

#### Projects
- `list_projects(status, ids, names, project_codes, parent_project_id, top_level_only, include, limit)` → `list[PersonioProject]`
- `get_project(project_id, include=None)` → `PersonioProject`
- `create_project(name, status="ACTIVE", parent_project_id=None, …)` → `PersonioProject`
- `update_project(project_id, **fields)` → `None` (HTTP 204)
- `delete_project(project_id)` → `None` (cascades to subprojects; raises `PersonioProblemError` 422 if attendance records exist)
- `list_project_members(project_id, limit=200)` → `list[dict]`

#### Attendance periods
- `list_attendance_periods(ids, person_ids, project_ids, start_gte/lte, end_gte/lte, attribution_date_gte/lte, status, sort, limit)` → `list[PersonioAttendancePeriod]`
- `get_attendance_period(period_id)` → `PersonioAttendancePeriod`
- `create_attendance_period(person_id, type, start, end=None, project_id=None, comment=None, skip_approval=False)` → `list[PersonioAttendancePeriod]`
- `update_attendance_period(period_id, skip_approval=False, **fields)` → `None`
- `delete_attendance_period(period_id)` → `None`

### V2 models

- `PersonioProject` — `id` (UUID `str`), `name`, `status` (`ACTIVE`/`ARCHIVED`),
  `assigned_to_all`, `parent_project`, `project_code`, `description`,
  `cost_center`, `start`, `end`, `billable`, `client_name`, `project_type`,
  plus any computed fields requested via `include[]`.
- `PersonioAttendancePeriod` — `id` (UUID), `person`, `type` (`WORK`/`BREAK`),
  `start`/`end` (datetime refs), `attribution_date`, `status`
  (`PENDING`/`CONFIRMED`/`REJECTED`), `project`, `comment`.

## Exceptions

- `PersonioError` - Base exception
- `PersonioConfigurationError` - Missing credentials
- `PersonioAuthenticationError` - Invalid credentials (401)
- `PersonioRateLimitError` - Rate limit exceeded (429)
- `PersonioProblemError` - V2 RFC 7807 error response (`type`, `title`, `detail`, `instance`)

## Development

```bash
# Clone repository
git clone https://github.com/dkd-dobberkau/personio-api-client
cd personio-api-client

# Install with dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Lint
uv run ruff check src/
uv run ruff format src/
```

## License

MIT
