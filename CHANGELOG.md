# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-05-05

### Added

- **`PersonioV2Client`** — new client targeting the Personio V2 API at
  `https://api.personio.de/v2`, separate from the existing V1 `PersonioClient`.
- **OAuth 2.0 `client_credentials` authentication** against `/v2/auth/token`
  with form-encoded body, token caching, and proactive refresh based on the
  `expires_in` field (60-second safety buffer).
- **Cursor-based pagination** helper covering all V2 list endpoints.
- **Projects (V2):** `list_projects`, `get_project`, `create_project`,
  `update_project`, `delete_project`, `list_project_members`. Supports filters
  by status, ids, names, project codes, parent project, and the `include[]`
  query for computed fields like `tracked_minutes` and `sub_projects_count`.
- **Attendance periods (V2):** `list_attendance_periods`,
  `get_attendance_period`, `create_attendance_period`,
  `update_attendance_period`, `delete_attendance_period`. Filters by person,
  project, datetime ranges, attribution date, and status. Create returns a
  list because the server may split a single submission into multiple periods.
  Validates that `BREAK` periods cannot be linked to a project. Honours the
  V2 `skip_approval` query parameter.
- **`PersonioProblemError`** exception that parses RFC 7807
  `application/problem+json` responses into `type` / `title` / `detail` /
  `instance` fields.
- **V2 models** — `PersonioProject`, `PersonioProjectRef`,
  `PersonioPersonRef`, `PersonioDateTimeRef`, `PersonioAttendancePeriod`.
  All accept unknown fields (`extra="allow"`) for forward compatibility.

### Changed

- `__init__.py` now also exports `PersonioV2Client` and `PersonioProblemError`.
- README documents both client versions side by side, including a V1-vs-V2
  comparison table covering auth, pagination, ID format, and error envelope.

### Notes

- The V1 client is unchanged. Personio is shutting down the V1 attendances and
  projects endpoints (`/v1/company/attendances` and
  `/v1/company/attendances/projects`) in 2026 — migrate to `PersonioV2Client`
  before then. The V1 endpoints for employees and time-offs (absences) are
  not affected by that deprecation.

## [0.1.0] — Initial release

- V1 client with employees, time-offs, and time-off types.
