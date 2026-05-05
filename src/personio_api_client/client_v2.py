"""
Personio REST API V2 Client (OAuth2 client_credentials).

Use this for the V2 attendances and projects endpoints. The V1 endpoints under
/v1/company/attendances and /v1/company/attendances/projects are deprecated by
Personio and scheduled to be turned off in 2026.

Example:
    from personio_api_client import PersonioV2Client

    with PersonioV2Client() as client:
        ...
"""

import logging
import os
import time
from collections.abc import Iterator
from datetime import date, datetime
from typing import Any, Literal

import httpx

from .exceptions import (
    PersonioAuthenticationError,
    PersonioConfigurationError,
    PersonioError,
    PersonioProblemError,
    PersonioRateLimitError,
)
from .models_v2 import PersonioAttendancePeriod, PersonioProject

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.personio.de/v2"

# Refresh the OAuth2 token this many seconds before its declared expiry
# to absorb clock skew and request latency.
TOKEN_EXPIRY_SAFETY_BUFFER_SECONDS = 60


class PersonioV2Client:
    """
    Python client for the Personio REST API V2.

    Args:
        client_id: Personio API Client ID. Falls back to PERSONIO_CLIENT_ID env var.
        client_secret: Personio API Client Secret. Falls back to PERSONIO_CLIENT_SECRET env var.
        base_url: API base URL (default: https://api.personio.de/v2).
        timeout: Request timeout in seconds (default: 30).

    Raises:
        PersonioConfigurationError: If credentials are not provided and not found in env.
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ):
        self.client_id = client_id or os.environ.get("PERSONIO_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("PERSONIO_CLIENT_SECRET")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        if not self.client_id or not self.client_secret:
            raise PersonioConfigurationError(
                "Personio credentials required. "
                "Pass client_id/client_secret or set PERSONIO_CLIENT_ID/PERSONIO_CLIENT_SECRET "
                "environment variables."
            )

        self._access_token: str | None = None
        self._token_expires_at: float | None = None
        self._client = httpx.Client(timeout=timeout)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        """Close the underlying HTTP client."""
        self._client.close()

    def _authenticate(self) -> str:
        """Obtain an OAuth2 access token via client_credentials grant.

        Returns the cached token while it is still valid; refreshes proactively
        before the declared expiry. When the server omits ``expires_in`` the
        token is cached indefinitely until the API returns 401.
        """
        if self._access_token and (
            self._token_expires_at is None
            or time.monotonic() < self._token_expires_at
        ):
            return self._access_token

        logger.debug("Authenticating with Personio V2 (client_credentials)...")

        try:
            response = self._client.post(
                f"{self.base_url}/auth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
        except httpx.HTTPError as e:
            raise PersonioError(f"HTTP error during authentication: {e}") from e

        if response.status_code == 401:
            raise PersonioAuthenticationError(
                "Invalid Personio credentials",
                status_code=401,
            )

        if response.status_code >= 400:
            raise PersonioAuthenticationError(
                f"Authentication failed (HTTP {response.status_code})",
                status_code=response.status_code,
            )

        data = response.json()
        token = data.get("access_token")
        if not token:
            raise PersonioAuthenticationError(
                "Authentication response missing access_token",
                response=data,
            )

        self._access_token = token
        expires_in = data.get("expires_in")
        if isinstance(expires_in, (int, float)) and expires_in > 0:
            self._token_expires_at = (
                time.monotonic() + expires_in - TOKEN_EXPIRY_SAFETY_BUFFER_SECONDS
            )
        else:
            self._token_expires_at = None
        return token

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> dict:
        """Perform an authenticated V2 API request and return parsed JSON."""
        token = self._authenticate()
        url = f"{self.base_url}{endpoint}"
        logger.debug("Personio V2 API: %s %s", method, url)

        response = self._send(method, url, token, params, json_data)

        if response.status_code == 401:
            # Token may have been revoked or expired; force re-auth and retry once.
            self._access_token = None
            self._token_expires_at = None
            token = self._authenticate()
            response = self._send(method, url, token, params, json_data)

        if response.status_code == 429:
            raise PersonioRateLimitError("Rate limit exceeded", status_code=429)

        if response.status_code >= 400:
            self._raise_for_error(response)

        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    def _send(
        self,
        method: str,
        url: str,
        token: str,
        params: dict | None,
        json_data: dict | None,
    ) -> "httpx.Response":
        try:
            return self._client.request(
                method=method,
                url=url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                params=params,
                json=json_data,
            )
        except httpx.HTTPError as e:
            raise PersonioError(f"HTTP error: {e}") from e

    @staticmethod
    def _raise_for_error(response: "httpx.Response") -> None:
        content_type = response.headers.get("Content-Type", "")
        body: dict | None = None
        if "json" in content_type:
            try:
                body = response.json()
            except ValueError:
                body = None

        if "application/problem+json" in content_type and isinstance(body, dict):
            raise PersonioProblemError(
                body.get("title") or f"HTTP {response.status_code}",
                status_code=response.status_code,
                problem=body,
            )

        raise PersonioError(
            f"HTTP {response.status_code}: {response.text[:200]}",
            status_code=response.status_code,
            response=body,
        )

    # NOTE: The list-response envelope shape (`data` + `_meta.next_cursor`) is
    # the documented Personio V2 pattern but the public reference does not show
    # rendered example bodies — confirm against the live API on first use.
    def _paginate(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Iterator[dict]:
        """Yield each item across all cursor-paginated pages."""
        params = dict(params or {})
        while True:
            page = self._request("GET", endpoint, params=params)
            yield from page.get("data", [])
            next_cursor = (page.get("_meta") or {}).get("next_cursor")
            if not next_cursor:
                return
            params["cursor"] = next_cursor

    # === Projects ===

    def list_projects(
        self,
        status: str | None = None,
        ids: list[str] | None = None,
        names: list[str] | None = None,
        project_codes: list[str] | None = None,
        parent_project_id: str | None = None,
        top_level_only: bool | None = None,
        include: list[str] | None = None,
        limit: int = 200,
    ) -> list[PersonioProject]:
        """List all projects matching the given filters.

        Args:
            status: ``"ACTIVE"`` or ``"ARCHIVED"``.
            ids: filter by project IDs.
            names: filter by exact project names.
            project_codes: filter by project codes.
            parent_project_id: filter to children of this parent.
            top_level_only: only return top-level projects.
            include: additional computed fields to include
                (e.g. ``"tracked_minutes"``, ``"sub_projects_count"``).
            limit: page size (1-200, default 200).
        """
        params: dict[str, Any] = {"limit": limit}
        if status is not None:
            params["status"] = status
        if ids:
            params["id[]"] = ids
        if names:
            params["name[]"] = names
        if project_codes:
            params["project_code[]"] = project_codes
        if parent_project_id is not None:
            params["parent_project.id[]"] = [parent_project_id]
        if top_level_only is not None:
            params["top_level_only"] = "true" if top_level_only else "false"
        if include:
            params["include[]"] = include

        items = self._paginate("/projects", params)
        return [PersonioProject.model_validate(item) for item in items]

    def get_project(
        self,
        project_id: str,
        include: list[str] | None = None,
    ) -> PersonioProject:
        """Fetch a single project by UUID."""
        params: dict[str, Any] | None = None
        if include:
            params = {"include[]": include}
        data = self._request("GET", f"/projects/{project_id}", params=params)
        return PersonioProject.model_validate(data)

    def create_project(
        self,
        name: str,
        status: str = "ACTIVE",
        parent_project_id: str | None = None,
        project_code: str | None = None,
        description: str | None = None,
        cost_center: str | None = None,
        start: str | None = None,
        end: str | None = None,
        billable: bool | None = None,
        client_name: str | None = None,
        project_type: str | None = None,
        assigned_to_all: bool | None = None,
    ) -> PersonioProject:
        """Create a project. Returns the created project."""
        body: dict[str, Any] = {"name": name, "status": status}
        if parent_project_id is not None:
            body["parent_project"] = {"id": parent_project_id}
        if project_code is not None:
            body["project_code"] = project_code
        if description is not None:
            body["description"] = description
        if cost_center is not None:
            body["cost_center"] = cost_center
        if start is not None:
            body["start"] = start
        if end is not None:
            body["end"] = end
        if billable is not None:
            body["billable"] = billable
        if client_name is not None:
            body["client_name"] = client_name
        if project_type is not None:
            body["project_type"] = project_type
        if assigned_to_all is not None:
            body["assigned_to_all"] = assigned_to_all

        data = self._request("POST", "/projects", json_data=body)
        return PersonioProject.model_validate(data)

    def update_project(self, project_id: str, **fields: Any) -> None:
        """Patch a project. Pass any subset of project fields as kwargs.

        ``parent_project_id`` is translated to ``parent_project={"id": ...}``.
        """
        body: dict[str, Any] = dict(fields)
        if "parent_project_id" in body:
            body["parent_project"] = {"id": body.pop("parent_project_id")}
        self._request("PATCH", f"/projects/{project_id}", json_data=body)
        return None

    def delete_project(self, project_id: str) -> None:
        """Delete a project. Cascades to subprojects.

        Raises:
            PersonioProblemError: 422 if the project (or a subproject) has
                attendance records.
        """
        self._request("DELETE", f"/projects/{project_id}")
        return None

    def list_project_members(
        self,
        project_id: str,
        limit: int = 200,
    ) -> list[dict]:
        """List employees assigned to a project.

        Returns raw member dicts; the V2 schema for project members is
        intentionally not modelled yet — confirm shape against the live API
        before introducing a typed model.
        """
        params: dict[str, Any] = {"limit": limit}
        return list(self._paginate(f"/projects/{project_id}/members", params))

    # === Attendance periods ===

    def list_attendance_periods(
        self,
        ids: list[str] | None = None,
        person_ids: list[str] | None = None,
        project_ids: list[str] | None = None,
        start_gte: datetime | None = None,
        start_lte: datetime | None = None,
        end_gte: datetime | None = None,
        end_lte: datetime | None = None,
        attribution_date_gte: date | None = None,
        attribution_date_lte: date | None = None,
        updated_at_gte: datetime | None = None,
        updated_at_lte: datetime | None = None,
        status: Literal["PENDING", "CONFIRMED", "REJECTED"] | None = None,
        sort: str | None = None,
        limit: int = 100,
    ) -> list[PersonioAttendancePeriod]:
        """List attendance periods matching the given filters.

        All datetime filters are serialized as ISO 8601. ``person_ids`` /
        ``project_ids`` translate to the dotted query keys ``person.id[]`` /
        ``project.id[]`` expected by Personio.
        """
        params: dict[str, Any] = {"limit": limit}
        if ids:
            params["id[]"] = ids
        if person_ids:
            params["person.id[]"] = person_ids
        if project_ids:
            params["project.id[]"] = project_ids
        if start_gte is not None:
            params["start.date_time.gte"] = start_gte.isoformat()
        if start_lte is not None:
            params["start.date_time.lte"] = start_lte.isoformat()
        if end_gte is not None:
            params["end.date_time.gte"] = end_gte.isoformat()
        if end_lte is not None:
            params["end.date_time.lte"] = end_lte.isoformat()
        if attribution_date_gte is not None:
            params["attribution_date.gte"] = attribution_date_gte.isoformat()
        if attribution_date_lte is not None:
            params["attribution_date.lte"] = attribution_date_lte.isoformat()
        if updated_at_gte is not None:
            params["updated_at.gte"] = updated_at_gte.isoformat()
        if updated_at_lte is not None:
            params["updated_at.lte"] = updated_at_lte.isoformat()
        if status is not None:
            params["status"] = status
        if sort is not None:
            params["sort"] = sort

        items = self._paginate("/attendance-periods", params)
        return [PersonioAttendancePeriod.model_validate(item) for item in items]

    def get_attendance_period(self, period_id: str) -> PersonioAttendancePeriod:
        """Fetch a single attendance period by UUID."""
        data = self._request("GET", f"/attendance-periods/{period_id}")
        return PersonioAttendancePeriod.model_validate(data)

    def create_attendance_period(
        self,
        person_id: str,
        type: Literal["WORK", "BREAK"],
        start: datetime,
        end: datetime | None = None,
        project_id: str | None = None,
        comment: str | None = None,
        skip_approval: bool = False,
    ) -> list[PersonioAttendancePeriod]:
        """Create one or more attendance periods.

        The server may split a single submission into multiple periods, so a
        list is always returned even if only one period was created.

        Args:
            person_id: UUID of the employee.
            type: ``"WORK"`` or ``"BREAK"``.
            start: Period start datetime.
            end: Period end datetime (may span midnight).
            project_id: Project assignment — only valid for ``type="WORK"``.
            comment: Optional comment.
            skip_approval: Skip the approval flow (V1 default behaviour).

        Raises:
            ValueError: When ``project_id`` is given on a ``BREAK`` period.
        """
        if type == "BREAK" and project_id is not None:
            raise ValueError("project_id cannot be set on a BREAK attendance period")

        body: dict[str, Any] = {
            "person": {"id": person_id},
            "type": type,
            "start": {"date_time": start.isoformat()},
        }
        if end is not None:
            body["end"] = {"date_time": end.isoformat()}
        if project_id is not None:
            body["project"] = {"id": project_id}
        if comment is not None:
            body["comment"] = comment

        params = {"skip_approval": "true"} if skip_approval else None

        data = self._request("POST", "/attendance-periods", params=params, json_data=body)
        items = data.get("data", []) if isinstance(data, dict) else []
        return [PersonioAttendancePeriod.model_validate(item) for item in items]

    def update_attendance_period(
        self,
        period_id: str,
        skip_approval: bool = False,
        **fields: Any,
    ) -> None:
        """Patch an attendance period. Pass any subset of mutable fields as kwargs."""
        params = {"skip_approval": "true"} if skip_approval else None
        self._request(
            "PATCH",
            f"/attendance-periods/{period_id}",
            params=params,
            json_data=dict(fields),
        )
        return None

    def delete_attendance_period(self, period_id: str) -> None:
        """Delete an attendance period."""
        self._request("DELETE", f"/attendance-periods/{period_id}")
        return None
