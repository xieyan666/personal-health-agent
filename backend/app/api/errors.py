"""Service exception to HTTP response mapping."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.services import (
    ConflictError,
    NotFoundError,
    ServiceError,
    ValidationError,
)


def register_service_exception_handlers(app: FastAPI) -> None:
    mappings = (
        (NotFoundError, 404),
        (ConflictError, 409),
        (ValidationError, 422),
        (ServiceError, 400),
    )

    for exception_type, status_code in mappings:
        async def handler(
            request: Request,
            exc: ServiceError,
            mapped_status: int = status_code,
        ) -> JSONResponse:
            del request
            return JSONResponse(
                status_code=mapped_status,
                content={"detail": str(exc)},
            )

        app.add_exception_handler(exception_type, handler)
