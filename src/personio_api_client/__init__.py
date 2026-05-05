"""
Personio API Client.

A Python client for the Personio REST API.

Example:
    from personio_api_client import PersonioClient

    # Using environment variables (PERSONIO_CLIENT_ID, PERSONIO_CLIENT_SECRET)
    with PersonioClient() as client:
        employees = client.get_employees()
        time_offs = client.get_time_offs(start_date=date(2025, 1, 1))

    # Or with explicit credentials
    client = PersonioClient(client_id="xxx", client_secret="yyy")
"""

from .client import PersonioClient
from .client_v2 import PersonioV2Client
from .exceptions import (
    PersonioAuthenticationError,
    PersonioConfigurationError,
    PersonioError,
    PersonioProblemError,
    PersonioRateLimitError,
)
from .models import (
    PersonioEmployee,
    PersonioTimeOff,
    PersonioTimeOffType,
    PersonioWorkSchedule,
)

__version__ = "0.1.0"

__all__ = [
    # Client
    "PersonioClient",
    "PersonioV2Client",
    # Exceptions
    "PersonioError",
    "PersonioConfigurationError",
    "PersonioAuthenticationError",
    "PersonioProblemError",
    "PersonioRateLimitError",
    # Models
    "PersonioEmployee",
    "PersonioTimeOff",
    "PersonioTimeOffType",
    "PersonioWorkSchedule",
]
