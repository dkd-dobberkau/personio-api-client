"""Exceptions for the Personio API client."""


class PersonioError(Exception):
    """Base exception for Personio API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response: dict | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class PersonioConfigurationError(PersonioError):
    """Configuration error (missing credentials)."""

    def __init__(self, message: str):
        super().__init__(message)


class PersonioAuthenticationError(PersonioError):
    """Authentication error (invalid credentials)."""

    pass


class PersonioRateLimitError(PersonioError):
    """Rate limit exceeded (HTTP 429)."""

    pass


class PersonioProblemError(PersonioError):
    """API error returned as RFC 7807 ``application/problem+json``.

    Used by the V2 client when Personio returns a structured problem detail
    document. Falls back to the raw response body when individual fields are
    missing.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        problem: dict | None = None,
    ):
        super().__init__(message, status_code=status_code, response=problem)
        problem = problem or {}
        self.type: str | None = problem.get("type")
        self.title: str | None = problem.get("title")
        self.detail: str | None = problem.get("detail")
        self.instance: str | None = problem.get("instance")
