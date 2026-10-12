from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Error de dominio con mensaje para el usuario y estado HTTP sugerido."""

    status = 400
    code = 'error'

    def __init__(self, message: str, *, hint: str | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {'error': self.code, 'message': self.message}
        if self.hint:
            data['hint'] = self.hint
        if self.details is not None:
            data['details'] = self.details
        return data


class NotFound(AppError):
    status = 404
    code = 'not_found'


class Conflict(AppError):
    status = 409
    code = 'conflict'


class Forbidden(AppError):
    status = 403
    code = 'forbidden'


class ValidationFailed(AppError):
    status = 422
    code = 'validation_failed'
