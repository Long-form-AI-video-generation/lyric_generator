"""Application exception types."""

from __future__ import annotations


class AppError(Exception):
    """Base error with an HTTP-ish status and public message."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        debug: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.debug = debug


class NotFoundError(AppError):
    """Raised when a job or asset cannot be found."""

    def __init__(self, message: str = "The requested resource was not found.") -> None:
        super().__init__(message, status_code=404)


class ValidationAppError(AppError):
    """Raised for user-correctable input validation failures."""

    def __init__(self, message: str, *, debug: str | None = None) -> None:
        super().__init__(message, status_code=422, debug=debug)


class WorkerUnavailableError(AppError):
    """Raised when async work cannot be queued."""

    def __init__(self, message: str = "The worker queue is unavailable.") -> None:
        super().__init__(message, status_code=503)

