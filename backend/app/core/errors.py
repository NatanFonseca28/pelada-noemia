"""Erros de domínio/serviço convertidos em respostas HTTP pelo handler em main.py."""


class AppError(Exception):
    status_code = 400

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class UnauthorizedError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class ValidationError(AppError):
    status_code = 422
