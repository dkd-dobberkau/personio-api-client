"""Tests for the Personio V2 API client (OAuth2 client_credentials)."""

from datetime import UTC

import pytest

from personio_api_client import (
    PersonioAuthenticationError,
    PersonioConfigurationError,
    PersonioProblemError,
    PersonioRateLimitError,
    PersonioV2Client,
)
from personio_api_client.models_v2 import PersonioAttendancePeriod, PersonioProject


def _mock_token(httpx_mock, token: str = "tkn-1"):
    httpx_mock.add_response(
        method="POST",
        url="https://api.personio.de/v2/auth/token",
        json={"access_token": token, "expires_in": 3600},
    )


class TestPersonioV2ClientConfiguration:
    def test_missing_credentials_raises_error(self, monkeypatch):
        monkeypatch.delenv("PERSONIO_CLIENT_ID", raising=False)
        monkeypatch.delenv("PERSONIO_CLIENT_SECRET", raising=False)

        with pytest.raises(PersonioConfigurationError) as exc_info:
            PersonioV2Client()

        assert "credentials required" in str(exc_info.value)

    def test_default_base_url_is_v2(self, monkeypatch):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        client = PersonioV2Client()

        assert client.base_url == "https://api.personio.de/v2"
        client.close()

    def test_custom_base_url_strips_trailing_slash(self, monkeypatch):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        client = PersonioV2Client(base_url="https://staging.personio.de/v2/")

        assert client.base_url == "https://staging.personio.de/v2"
        client.close()

    def test_context_manager_closes_client(self, monkeypatch):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        with PersonioV2Client() as client:
            assert client.client_id == "test-id"


class TestPersonioV2ClientAuthentication:
    def test_authenticate_posts_form_encoded_client_credentials(
        self, monkeypatch, httpx_mock
    ):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        httpx_mock.add_response(
            method="POST",
            url="https://api.personio.de/v2/auth/token",
            json={"access_token": "abc-123", "token_type": "Bearer", "expires_in": 3600},
        )

        with PersonioV2Client() as client:
            token = client._authenticate()

        assert token == "abc-123"

        request = httpx_mock.get_request()
        assert request.headers["Content-Type"].startswith(
            "application/x-www-form-urlencoded"
        )
        body = request.content.decode()
        assert "grant_type=client_credentials" in body
        assert "client_id=test-id" in body
        assert "client_secret=test-secret" in body

    def test_authenticate_401_raises_authentication_error(
        self, monkeypatch, httpx_mock
    ):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "bad-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "bad-secret")

        httpx_mock.add_response(
            method="POST",
            url="https://api.personio.de/v2/auth/token",
            status_code=401,
            json={"error": "invalid_client"},
        )

        with PersonioV2Client() as client, pytest.raises(PersonioAuthenticationError):
            client._authenticate()

    def test_token_cached_across_authenticate_calls(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        # Only ONE response queued — second call must reuse cached token.
        httpx_mock.add_response(
            method="POST",
            url="https://api.personio.de/v2/auth/token",
            json={"access_token": "cached-token", "expires_in": 3600},
        )

        with PersonioV2Client() as client:
            first = client._authenticate()
            second = client._authenticate()

        assert first == second == "cached-token"
        assert len(httpx_mock.get_requests()) == 1

    def test_expired_token_triggers_proactive_refresh(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        httpx_mock.add_response(
            method="POST",
            url="https://api.personio.de/v2/auth/token",
            json={"access_token": "first-token", "expires_in": 60},
        )
        httpx_mock.add_response(
            method="POST",
            url="https://api.personio.de/v2/auth/token",
            json={"access_token": "second-token", "expires_in": 3600},
        )

        with PersonioV2Client() as client:
            first = client._authenticate()
            # Force the cached expiry into the past — simulates time passing.
            client._token_expires_at = 0.0
            second = client._authenticate()

        assert first == "first-token"
        assert second == "second-token"
        assert len(httpx_mock.get_requests()) == 2

    def test_no_proactive_refresh_when_expires_in_missing(
        self, monkeypatch, httpx_mock
    ):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        # No expires_in -> client must not gamble on TTL; cache the token until 401.
        httpx_mock.add_response(
            method="POST",
            url="https://api.personio.de/v2/auth/token",
            json={"access_token": "ttl-less-token"},
        )

        with PersonioV2Client() as client:
            client._authenticate()
            client._authenticate()

        assert len(httpx_mock.get_requests()) == 1


class TestPersonioV2ClientRequest:
    @staticmethod
    def _mock_token(httpx_mock, token: str = "tkn-1"):
        httpx_mock.add_response(
            method="POST",
            url="https://api.personio.de/v2/auth/token",
            json={"access_token": token, "expires_in": 3600},
        )

    def test_get_sends_bearer_token_and_returns_json(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        self._mock_token(httpx_mock, "live-token")
        httpx_mock.add_response(
            method="GET",
            url="https://api.personio.de/v2/projects?limit=10",
            json={"items": [], "cursor": None},
        )

        with PersonioV2Client() as client:
            data = client._request("GET", "/projects", params={"limit": 10})

        assert data == {"items": [], "cursor": None}

        api_request = httpx_mock.get_requests()[1]
        assert api_request.headers["Authorization"] == "Bearer live-token"
        assert api_request.headers["Accept"] == "application/json"

    def test_401_response_triggers_reauth_and_retry(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        # First token, then a 401 from the API, then a fresh token, then success.
        httpx_mock.add_response(
            method="POST",
            url="https://api.personio.de/v2/auth/token",
            json={"access_token": "stale-token", "expires_in": 3600},
        )
        httpx_mock.add_response(
            method="GET",
            url="https://api.personio.de/v2/projects",
            status_code=401,
            json={"error": "token expired"},
        )
        httpx_mock.add_response(
            method="POST",
            url="https://api.personio.de/v2/auth/token",
            json={"access_token": "fresh-token", "expires_in": 3600},
        )
        httpx_mock.add_response(
            method="GET",
            url="https://api.personio.de/v2/projects",
            json={"items": ["ok"]},
        )

        with PersonioV2Client() as client:
            data = client._request("GET", "/projects")

        assert data == {"items": ["ok"]}

        # The retry should have used the fresh token.
        api_calls = [r for r in httpx_mock.get_requests() if r.url.path == "/v2/projects"]
        assert api_calls[-1].headers["Authorization"] == "Bearer fresh-token"

    def test_429_raises_rate_limit_error(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        self._mock_token(httpx_mock)
        httpx_mock.add_response(
            method="GET",
            url="https://api.personio.de/v2/projects",
            status_code=429,
            json={"error": "rate limited"},
        )

        with PersonioV2Client() as client, pytest.raises(PersonioRateLimitError) as exc:
            client._request("GET", "/projects")

        assert exc.value.status_code == 429

    def test_problem_json_response_raises_problem_error(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        self._mock_token(httpx_mock)
        httpx_mock.add_response(
            method="GET",
            url="https://api.personio.de/v2/projects/abc",
            status_code=404,
            headers={"Content-Type": "application/problem+json"},
            json={
                "type": "https://developer.personio.de/errors/not-found",
                "title": "Project not found",
                "status": 404,
                "detail": "No project with id 'abc'",
                "instance": "/v2/projects/abc",
            },
        )

        with PersonioV2Client() as client, pytest.raises(PersonioProblemError) as exc:
            client._request("GET", "/projects/abc")

        problem = exc.value
        assert problem.status_code == 404
        assert problem.title == "Project not found"
        assert problem.detail == "No project with id 'abc'"
        assert problem.type == "https://developer.personio.de/errors/not-found"
        assert problem.instance == "/v2/projects/abc"


PROJECT_FIXTURE = {
    "id": "11111111-1111-1111-1111-111111111111",
    "name": "Internal R&D",
    "status": "ACTIVE",
    "assigned_to_all": True,
    "project_code": "RND-001",
    "description": "Research budget",
    "parent_project": None,
}


class TestPersonioV2Projects:
    def test_list_projects_single_page(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)
        httpx_mock.add_response(
            method="GET",
            url="https://api.personio.de/v2/projects?limit=200",
            json={"data": [PROJECT_FIXTURE], "_meta": {"next_cursor": None}},
        )

        with PersonioV2Client() as client:
            projects = client.list_projects()

        assert len(projects) == 1
        assert isinstance(projects[0], PersonioProject)
        assert projects[0].id == "11111111-1111-1111-1111-111111111111"
        assert projects[0].name == "Internal R&D"
        assert projects[0].status == "ACTIVE"
        assert projects[0].assigned_to_all is True
        assert projects[0].project_code == "RND-001"

    def test_list_projects_follows_cursor_through_pages(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)

        page_1 = {
            "data": [{**PROJECT_FIXTURE, "id": "p-1", "name": "P1"}],
            "_meta": {"next_cursor": "CURSOR-2"},
        }
        page_2 = {
            "data": [{**PROJECT_FIXTURE, "id": "p-2", "name": "P2"}],
            "_meta": {"next_cursor": None},
        }
        httpx_mock.add_response(
            method="GET",
            url="https://api.personio.de/v2/projects?limit=200",
            json=page_1,
        )
        httpx_mock.add_response(
            method="GET",
            url="https://api.personio.de/v2/projects?limit=200&cursor=CURSOR-2",
            json=page_2,
        )

        with PersonioV2Client() as client:
            projects = client.list_projects()

        assert [p.id for p in projects] == ["p-1", "p-2"]

    def test_list_projects_passes_filters_and_include(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)
        httpx_mock.add_response(
            method="GET",
            json={"data": [], "_meta": {"next_cursor": None}},
        )

        with PersonioV2Client() as client:
            client.list_projects(
                status="ACTIVE",
                top_level_only=True,
                include=["tracked_minutes", "sub_projects_count"],
                limit=50,
            )

        request = httpx_mock.get_requests()[1]
        query = request.url.query.decode()
        assert "status=ACTIVE" in query
        assert "top_level_only=true" in query
        assert "include%5B%5D=tracked_minutes" in query
        assert "include%5B%5D=sub_projects_count" in query
        assert "limit=50" in query

    def test_get_project_by_id(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)
        httpx_mock.add_response(
            method="GET",
            url="https://api.personio.de/v2/projects/abc-123",
            json=PROJECT_FIXTURE,
        )

        with PersonioV2Client() as client:
            project = client.get_project("abc-123")

        assert isinstance(project, PersonioProject)
        assert project.id == "11111111-1111-1111-1111-111111111111"

    def test_create_project_minimal(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)
        httpx_mock.add_response(
            method="POST",
            url="https://api.personio.de/v2/projects",
            status_code=201,
            json={**PROJECT_FIXTURE, "id": "new-uuid", "name": "Phoenix"},
        )

        with PersonioV2Client() as client:
            created = client.create_project(name="Phoenix")

        assert created.id == "new-uuid"
        assert created.name == "Phoenix"

        request = httpx_mock.get_requests()[1]
        import json as _json

        body = _json.loads(request.content)
        assert body["name"] == "Phoenix"
        assert body["status"] == "ACTIVE"

    def test_create_project_with_parent(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)
        httpx_mock.add_response(
            method="POST",
            url="https://api.personio.de/v2/projects",
            status_code=201,
            json={
                **PROJECT_FIXTURE,
                "id": "child-id",
                "name": "Child",
                "parent_project": {"id": "parent-id"},
            },
        )

        with PersonioV2Client() as client:
            created = client.create_project(
                name="Child",
                parent_project_id="parent-id",
                project_code="CHD-1",
            )

        assert created.parent_project is not None
        assert created.parent_project.id == "parent-id"

        import json as _json

        body = _json.loads(httpx_mock.get_requests()[1].content)
        assert body["parent_project"] == {"id": "parent-id"}
        assert body["project_code"] == "CHD-1"

    def test_update_project_returns_none_on_204(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)
        httpx_mock.add_response(
            method="PATCH",
            url="https://api.personio.de/v2/projects/abc-123",
            status_code=204,
        )

        with PersonioV2Client() as client:
            result = client.update_project("abc-123", status="ARCHIVED")

        assert result is None

        import json as _json

        body = _json.loads(httpx_mock.get_requests()[1].content)
        assert body == {"status": "ARCHIVED"}

    def test_delete_project_204(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)
        httpx_mock.add_response(
            method="DELETE",
            url="https://api.personio.de/v2/projects/abc-123",
            status_code=204,
        )

        with PersonioV2Client() as client:
            result = client.delete_project("abc-123")

        assert result is None

    def test_delete_project_in_use_raises_problem_error(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)
        httpx_mock.add_response(
            method="DELETE",
            url="https://api.personio.de/v2/projects/abc-123",
            status_code=422,
            headers={"Content-Type": "application/problem+json"},
            json={
                "type": "https://developer.personio.de/errors/project-in-use",
                "title": "Project has attendance records",
                "status": 422,
                "detail": "Cannot delete project with existing tracked time",
            },
        )

        with PersonioV2Client() as client, pytest.raises(PersonioProblemError) as exc:
            client.delete_project("abc-123")

        assert exc.value.status_code == 422
        assert exc.value.title == "Project has attendance records"

    def test_list_project_members_paginated(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)
        page_1 = {
            "data": [{"id": "emp-1"}, {"id": "emp-2"}],
            "_meta": {"next_cursor": "C2"},
        }
        page_2 = {
            "data": [{"id": "emp-3"}],
            "_meta": {"next_cursor": None},
        }
        httpx_mock.add_response(
            method="GET",
            url="https://api.personio.de/v2/projects/abc/members?limit=200",
            json=page_1,
        )
        httpx_mock.add_response(
            method="GET",
            url="https://api.personio.de/v2/projects/abc/members?limit=200&cursor=C2",
            json=page_2,
        )

        with PersonioV2Client() as client:
            members = client.list_project_members("abc")

        assert [m["id"] for m in members] == ["emp-1", "emp-2", "emp-3"]


ATTENDANCE_FIXTURE = {
    "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "person": {"id": "emp-100"},
    "type": "WORK",
    "start": {"date_time": "2026-05-04T08:00:00Z"},
    "end": {"date_time": "2026-05-04T16:30:00Z"},
    "attribution_date": "2026-05-04",
    "status": "CONFIRMED",
    "project": {"id": "proj-1"},
    "comment": None,
}


class TestPersonioV2Attendances:
    def test_list_attendance_periods_single_page(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)
        httpx_mock.add_response(
            method="GET",
            url="https://api.personio.de/v2/attendance-periods?limit=100",
            json={"data": [ATTENDANCE_FIXTURE], "_meta": {"next_cursor": None}},
        )

        with PersonioV2Client() as client:
            periods = client.list_attendance_periods()

        assert len(periods) == 1
        assert isinstance(periods[0], PersonioAttendancePeriod)
        assert periods[0].id == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        assert periods[0].person.id == "emp-100"
        assert periods[0].type == "WORK"
        assert periods[0].status == "CONFIRMED"
        assert periods[0].project is not None
        assert periods[0].project.id == "proj-1"

    def test_list_attendance_periods_passes_filters(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)
        httpx_mock.add_response(
            method="GET",
            json={"data": [], "_meta": {"next_cursor": None}},
        )

        from datetime import date, datetime

        with PersonioV2Client() as client:
            client.list_attendance_periods(
                person_ids=["emp-1", "emp-2"],
                project_ids=["proj-1"],
                start_gte=datetime(2026, 5, 1, tzinfo=UTC),
                end_lte=datetime(2026, 5, 31, 23, 59, tzinfo=UTC),
                attribution_date_gte=date(2026, 5, 1),
                status="CONFIRMED",
                limit=50,
            )

        request = httpx_mock.get_requests()[1]
        query = request.url.query.decode()
        assert "person.id%5B%5D=emp-1" in query
        assert "person.id%5B%5D=emp-2" in query
        assert "project.id%5B%5D=proj-1" in query
        assert "status=CONFIRMED" in query
        assert "limit=50" in query
        # ISO 8601 datetimes (URL-encoded colons appear as %3A)
        assert "start.date_time.gte=2026-05-01" in query
        assert "end.date_time.lte=2026-05-31" in query
        assert "attribution_date.gte=2026-05-01" in query

    def test_get_attendance_period(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)
        httpx_mock.add_response(
            method="GET",
            url="https://api.personio.de/v2/attendance-periods/some-uuid",
            json=ATTENDANCE_FIXTURE,
        )

        with PersonioV2Client() as client:
            period = client.get_attendance_period("some-uuid")

        assert isinstance(period, PersonioAttendancePeriod)
        assert period.type == "WORK"

    def test_create_attendance_period_returns_list(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)
        # Server may split a single create into multiple periods; client returns a list.
        httpx_mock.add_response(
            method="POST",
            url="https://api.personio.de/v2/attendance-periods?skip_approval=true",
            status_code=201,
            json={"data": [ATTENDANCE_FIXTURE]},
        )

        from datetime import datetime

        with PersonioV2Client() as client:
            created = client.create_attendance_period(
                person_id="emp-100",
                type="WORK",
                start=datetime(2026, 5, 4, 8, 0, tzinfo=UTC),
                end=datetime(2026, 5, 4, 16, 30, tzinfo=UTC),
                project_id="proj-1",
                skip_approval=True,
            )

        assert isinstance(created, list)
        assert len(created) == 1
        assert created[0].id == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        request = httpx_mock.get_requests()[1]
        assert "skip_approval=true" in request.url.query.decode()

        import json as _json

        body = _json.loads(request.content)
        assert body["person"] == {"id": "emp-100"}
        assert body["type"] == "WORK"
        assert body["project"] == {"id": "proj-1"}
        assert body["start"]["date_time"].startswith("2026-05-04T08:00:00")

    def test_create_attendance_period_break_rejects_project(self, monkeypatch):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        from datetime import datetime

        with PersonioV2Client() as client, pytest.raises(ValueError) as exc:
            client.create_attendance_period(
                person_id="emp-100",
                type="BREAK",
                start=datetime(2026, 5, 4, 12, 0, tzinfo=UTC),
                end=datetime(2026, 5, 4, 12, 30, tzinfo=UTC),
                project_id="proj-1",
            )

        assert "BREAK" in str(exc.value)

    def test_update_attendance_period_204(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)
        httpx_mock.add_response(
            method="PATCH",
            url="https://api.personio.de/v2/attendance-periods/some-uuid?skip_approval=true",
            status_code=204,
        )

        with PersonioV2Client() as client:
            result = client.update_attendance_period(
                "some-uuid",
                comment="Updated note",
                skip_approval=True,
            )

        assert result is None

        request = httpx_mock.get_requests()[1]
        assert "skip_approval=true" in request.url.query.decode()

        import json as _json

        body = _json.loads(request.content)
        assert body == {"comment": "Updated note"}

    def test_delete_attendance_period_204(self, monkeypatch, httpx_mock):
        monkeypatch.setenv("PERSONIO_CLIENT_ID", "test-id")
        monkeypatch.setenv("PERSONIO_CLIENT_SECRET", "test-secret")

        _mock_token(httpx_mock)
        httpx_mock.add_response(
            method="DELETE",
            url="https://api.personio.de/v2/attendance-periods/some-uuid",
            status_code=204,
        )

        with PersonioV2Client() as client:
            result = client.delete_attendance_period("some-uuid")

        assert result is None
