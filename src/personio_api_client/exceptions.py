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
