"""Tests for Personio client."""

import pytest

from personio_api_client import (
    PersonioAuthenticationError,
    PersonioClient,
    PersonioConfigurationError,
)


class TestPersonioClientConfiguration:
    def test_missing_credentials_raises_error(self, monkeypatch):
        """Test that missing credentials raise PersonioConfigurationError."""
        monkeypatch.delenv("PERSONIO_CLIENT_ID", raising=False)
        monkeypatch.delenv("PERSONIO_CLIENT_SECRET", raising=False)

        with pytest.raises(PersonioConfigurationError) as exc_info:
            PersonioClient()

        assert "credentials required" in str(exc_info.value)

    def test_explicit_credentials(self, monkeypatch):
        """Test that explicit credentials work."""
        monkeypatch.delenv("PERSONIO_CLIENT_ID", raising=False)
        monkeypatch.delenv("PERSONIO_CLIENT_SECRET", raising=False)

        client = PersonioClient(
            client_id="test-id",
            client_secret="test-secret",
        )

        assert client.client_id == "test-id"
        assert client.client_secret == "test-secret"
        client.close()

    def test_env_credentials(self, monkeypatch):
        """Test that environment credentials work."""
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "env-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "env-secret")

        client = PersonioClient()

        assert client.client_id == "env-id"
        assert client.client_secret == "env-secret"
        client.close()

    def test_explicit_overrides_env(self, monkeypatch):
        """Test that explicit credentials override environment."""
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "env-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "env-secret")

        client = PersonioClient(
            client_id="explicit-id",
            client_secret="explicit-secret",
        )

        assert client.client_id == "explicit-id"
        assert client.client_secret == "explicit-secret"
        client.close()

    def test_custom_base_url(self, monkeypatch):
        """Test custom base URL."""
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        client = PersonioClient(base_url="https://custom.personio.de/v1/")

        assert client.base_url == "https://custom.personio.de/v1"  # trailing slash removed
        client.close()

    def test_custom_timeout(self, monkeypatch):
        """Test custom timeout."""
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        client = PersonioClient(timeout=60.0)

        assert client.timeout == 60.0
        client.close()


class TestPersonioClientContextManager:
    def test_context_manager(self, monkeypatch):
        """Test that context manager works."""
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        with PersonioClient() as client:
            assert client.client_id == "test-id"


class TestPersonioClientAuthentication:
    def test_authentication_error(self, monkeypatch, httpx_mock):
        """Test that 401 raises PersonioAuthenticationError."""
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        httpx_mock.add_response(
            url="https://api.personio.de/v1/auth?client_id=test-id&client_secret=test-secret",
            status_code=401,
        )

        client = PersonioClient()

        with pytest.raises(PersonioAuthenticationError):
            client.get_employees()

        client.close()

    def test_successful_authentication(self, monkeypatch, httpx_mock):
        """Test successful authentication flow."""
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        # Mock auth response
        httpx_mock.add_response(
            url="https://api.personio.de/v1/auth?client_id=test-id&client_secret=test-secret",
            json={"success": True, "data": {"token": "test-token"}},
        )

        # Mock employees response
        httpx_mock.add_response(
            url="https://api.personio.de/v1/company/employees?limit=200&offset=0",
            json={"success": True, "data": []},
        )

        client = PersonioClient()
        employees = client.get_employees()

        assert employees == []
        client.close()


class TestPersonioClientEmployees:
    def test_get_employees(self, monkeypatch, httpx_mock):
        """Test getting employees."""
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        httpx_mock.add_response(
            url="https://api.personio.de/v1/auth?client_id=test-id&client_secret=test-secret",
            json={"success": True, "data": {"token": "test-token"}},
        )

        httpx_mock.add_response(
            url="https://api.personio.de/v1/company/employees?limit=200&offset=0",
            json={
                "success": True,
                "data": [
                    {
                        "id": 1,
                        "attributes": {
                            "id": {"value": 1},
                            "email": {"value": "john@example.com"},
                            "first_name": {"value": "John"},
                            "last_name": {"value": "Doe"},
                            "status": {"value": "active"},
                        },
                    }
                ],
            },
        )

        with PersonioClient() as client:
            employees = client.get_employees()

        assert len(employees) == 1
        assert employees[0].id == 1
        assert employees[0].email == "john@example.com"
        assert employees[0].name == "John Doe"


class TestPersonioClientTimeOffs:
    def test_get_time_offs(self, monkeypatch, httpx_mock):
        """Test getting time-offs."""
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        httpx_mock.add_response(
            url="https://api.personio.de/v1/auth?client_id=test-id&client_secret=test-secret",
            json={"success": True, "data": {"token": "test-token"}},
        )

        httpx_mock.add_response(
            json={
                "success": True,
                "data": [
                    {
                        "id": 1,
                        "attributes": {
                            "id": 1,
                            "start_date": "2025-01-01",
                            "end_date": "2025-01-05",
                            "days_count": 5,
                            "status": "approved",
                            "employee": {
                                "id": 100,
                                "attributes": {
                                    "id": {"value": 100},
                                    "email": {"value": "john@example.com"},
                                    "first_name": {"value": "John"},
                                    "last_name": {"value": "Doe"},
                                },
                            },
                            "time_off_type": {
                                "attributes": {
                                    "id": 1,
                                    "name": "Vacation",
                                },
                            },
                        },
                    }
                ],
            },
        )

        from datetime import date

        with PersonioClient() as client:
            time_offs = client.get_time_offs(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 31),
            )

        assert len(time_offs) == 1
        assert time_offs[0].employee_name == "John Doe"
        assert time_offs[0].time_off_type_name == "Vacation"
        assert time_offs[0].days_count == 5
