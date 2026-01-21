# personio-api-client

Python client for the [Personio](https://www.personio.de/) REST API.

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

## Exceptions

- `PersonioError` - Base exception
- `PersonioConfigurationError` - Missing credentials
- `PersonioAuthenticationError` - Invalid credentials (401)
- `PersonioRateLimitError` - Rate limit exceeded (429)

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
