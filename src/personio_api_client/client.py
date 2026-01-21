"""
Personio REST API Client.

Example:
    from personio_api_client import PersonioClient

    # Using environment variables (PERSONIO_CLIENT_ID, PERSONIO_CLIENT_SECRET)
    with PersonioClient() as client:
        employees = client.get_employees()
        time_offs = client.get_time_offs(start_date=date(2025, 1, 1))

    # Or with explicit credentials
    client = PersonioClient(client_id="xxx", client_secret="yyy")
"""

import logging
import os
from datetime import date
from typing import Any

import httpx

from .exceptions import (
    PersonioAuthenticationError,
    PersonioConfigurationError,
    PersonioError,
    PersonioRateLimitError,
)
from .models import PersonioEmployee, PersonioTimeOff, PersonioTimeOffType, PersonioWorkSchedule

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.personio.de/v1"


class PersonioClient:
    """
    Python client for the Personio REST API.

    Args:
        client_id: Personio API Client ID. Falls back to PERSONIO_CLIENT_ID env var.
        client_secret: Personio API Client Secret. Falls back to PERSONIO_CLIENT_SECRET env var.
        base_url: API base URL (default: https://api.personio.de/v1)
        timeout: Request timeout in seconds (default: 30)

    Raises:
        PersonioConfigurationError: If credentials are not provided and not found in env.

    Example:
        # Using environment variables
        client = PersonioClient()

        # Or explicit credentials
        client = PersonioClient(
            client_id="your-client-id",
            client_secret="your-client-secret"
        )

        # Get employees
        employees = client.get_employees()

        # Get time-offs
        time_offs = client.get_time_offs(start_date=date(2025, 1, 1))
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
        self._client = httpx.Client(timeout=timeout)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def _authenticate(self) -> str:
        """Authenticate and return access token."""
        if self._access_token:
            return self._access_token

        logger.debug("Authenticating with Personio...")

        try:
            response = self._client.post(
                f"{self.base_url}/auth",
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )

            if response.status_code == 401:
                raise PersonioAuthenticationError(
                    "Invalid Personio credentials",
                    status_code=401,
                )

            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                raise PersonioAuthenticationError(
                    f"Authentication failed: {data.get('error', 'Unknown error')}",
                )

            self._access_token = data["data"]["token"]
            logger.debug("Personio authentication successful")
            return self._access_token

        except httpx.HTTPStatusError as e:
            raise PersonioError(
                f"HTTP error during authentication: {e}",
                status_code=e.response.status_code,
            ) from e

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> dict:
        """Perform an authenticated API request."""
        token = self._authenticate()

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        url = f"{self.base_url}{endpoint}"
        logger.debug("Personio API: %s %s", method, url)

        try:
            response = self._client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
            )

            if response.status_code == 401:
                # Token expired, re-authenticate
                self._access_token = None
                token = self._authenticate()
                headers["Authorization"] = f"Bearer {token}"
                response = self._client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                )

            if response.status_code == 429:
                raise PersonioRateLimitError(
                    "Rate limit exceeded",
                    status_code=429,
                )

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            raise PersonioError(
                f"HTTP error: {e}",
                status_code=e.response.status_code,
            ) from e

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """Perform a GET request."""
        return self._request("GET", endpoint, params=params)

    # === Employees ===

    def get_employees(self, active_only: bool = True) -> list[PersonioEmployee]:
        """
        Get all employees from Personio.

        Args:
            active_only: Only return active employees (default: True)

        Returns:
            List of PersonioEmployee objects
        """
        logger.info("Loading Personio employees...")
        employees = []
        offset = 0
        limit = 200

        while True:
            response = self._get(
                "/company/employees",
                params={"limit": limit, "offset": offset},
            )

            if not response.get("success"):
                raise PersonioError(f"Failed to load employees: {response}")

            data = response.get("data", [])
            if not data:
                break

            for emp_data in data:
                attrs = emp_data.get("attributes", {})

                def get_attr(name: str, attrs: dict = attrs) -> Any:
                    attr = attrs.get(name, {})
                    return attr.get("value") if isinstance(attr, dict) else attr

                def get_nested_name(name: str, get_attr: Any = get_attr) -> str | None:
                    val = get_attr(name)
                    if isinstance(val, dict) and "attributes" in val:
                        return val["attributes"].get("name")
                    return val if isinstance(val, str) else None

                status = get_attr("status")
                if active_only and status != "active":
                    continue

                # Parse work schedule if available
                work_schedule = None
                ws_data = get_attr("work_schedule")
                if isinstance(ws_data, dict) and ws_data.get("type") == "WorkSchedule":
                    ws_attrs = ws_data.get("attributes", {})
                    work_schedule = PersonioWorkSchedule(
                        id=ws_attrs.get("id", 0),
                        name=ws_attrs.get("name", ""),
                        valid_from=ws_attrs.get("valid_from"),
                        monday=ws_attrs.get("monday", "00:00"),
                        tuesday=ws_attrs.get("tuesday", "00:00"),
                        wednesday=ws_attrs.get("wednesday", "00:00"),
                        thursday=ws_attrs.get("thursday", "00:00"),
                        friday=ws_attrs.get("friday", "00:00"),
                        saturday=ws_attrs.get("saturday", "00:00"),
                        sunday=ws_attrs.get("sunday", "00:00"),
                    )

                # Parse weekly working hours
                weekly_hours = get_attr("weekly_working_hours")
                if isinstance(weekly_hours, str):
                    weekly_hours = float(weekly_hours) if weekly_hours else None

                employee = PersonioEmployee(
                    id=get_attr("id") or emp_data.get("id"),
                    email=get_attr("email"),
                    first_name=get_attr("first_name"),
                    last_name=get_attr("last_name"),
                    status=status,
                    department=get_nested_name("department"),
                    team=get_nested_name("team"),
                    position=get_attr("position"),
                    hire_date=get_attr("hire_date"),
                    termination_date=get_attr("termination_date"),
                    weekly_working_hours=weekly_hours,
                    work_schedule=work_schedule,
                )
                employees.append(employee)

            offset += limit
            if len(data) < limit:
                break

        logger.info("Personio: %d employees loaded", len(employees))
        return employees

    # === Time-Offs (Absences) ===

    def get_time_off_types(self) -> list[PersonioTimeOffType]:
        """
        Get all time-off types.

        Returns:
            List of PersonioTimeOffType objects
        """
        logger.info("Loading Personio time-off types...")

        response = self._get("/company/time-off-types")

        if not response.get("success"):
            raise PersonioError(f"Failed to load time-off types: {response}")

        types = []
        for type_data in response.get("data", []):
            attrs = type_data.get("attributes", {})
            types.append(
                PersonioTimeOffType(
                    id=attrs.get("id", type_data.get("id")),
                    name=attrs.get("name", ""),
                    category=attrs.get("category"),
                )
            )

        logger.info("Personio: %d time-off types loaded", len(types))
        return types

    def get_time_offs(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        employee_ids: list[int] | None = None,
    ) -> list[PersonioTimeOff]:
        """
        Get time-offs (vacation, sick leave, etc.) from Personio.

        Args:
            start_date: Filter start date
            end_date: Filter end date
            employee_ids: Optional: only for these employees

        Returns:
            List of PersonioTimeOff objects
        """
        logger.info("Loading Personio time-offs (%s - %s)...", start_date, end_date)
        time_offs = []
        offset = 0
        limit = 200

        params: dict[str, Any] = {"limit": limit}
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()
        if employee_ids:
            params["employees[]"] = employee_ids

        while True:
            params["offset"] = offset
            response = self._get("/company/time-offs", params=params)

            if not response.get("success"):
                raise PersonioError(f"Failed to load time-offs: {response}")

            data = response.get("data", [])
            if not data:
                break

            for entry in data:
                attrs = entry.get("attributes", {})

                # Extract nested employee data
                employee = attrs.get("employee", {})
                emp_attrs = employee.get("attributes", {})

                def get_emp_attr(name: str, emp_attrs: dict = emp_attrs) -> Any:
                    attr = emp_attrs.get(name, {})
                    return attr.get("value") if isinstance(attr, dict) else attr

                # Extract time-off type
                time_off_type = attrs.get("time_off_type", {})
                type_attrs = time_off_type.get("attributes", {})

                time_off = PersonioTimeOff(
                    id=attrs.get("id", entry.get("id")),
                    employee_id=get_emp_attr("id") or employee.get("id"),
                    employee_email=get_emp_attr("email"),
                    employee_first_name=get_emp_attr("first_name"),
                    employee_last_name=get_emp_attr("last_name"),
                    time_off_type_id=type_attrs.get("id", 0),
                    time_off_type_name=type_attrs.get("name", "Unbekannt"),
                    start_date=attrs.get("start_date"),
                    end_date=attrs.get("end_date"),
                    days_count=attrs.get("days_count", 0),
                    half_day_start=attrs.get("half_day_start", False),
                    half_day_end=attrs.get("half_day_end", False),
                    status=attrs.get("status", "approved"),
                    comment=attrs.get("comment"),
                )
                time_offs.append(time_off)

            offset += limit
            if len(data) < limit:
                break

        logger.info("Personio: %d time-offs loaded", len(time_offs))
        return time_offs
