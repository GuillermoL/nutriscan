"""Mapeo de excepciones de dominio a respuestas HTTP con el JSON de error.

Formato único: {"error": {"code", "message", "hint"}}. Un handler global
captura lo inesperado como 500, sin filtrar la traza al cliente.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.errors import (
    CorruptFileError,
    FileTooLargeError,
    LabelExtractionError,
    NoNutritionTableError,
    NoTextDetectedError,
    OcrEngineUnavailableError,
    UnsupportedFormatError,
)
from app.domain.traffic_light import InvalidTrafficLightConfigError

logger = logging.getLogger("nutriscan")

HTTP_STATUS_BY_EXCEPTION: dict[type[LabelExtractionError], int] = {
    UnsupportedFormatError: 415,
    FileTooLargeError: 413,
    CorruptFileError: 422,
    NoTextDetectedError: 422,
    NoNutritionTableError: 422,
    OcrEngineUnavailableError: 503,
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(LabelExtractionError)
    async def handle_label_extraction_error(request: Request, exc: LabelExtractionError) -> JSONResponse:
        status_code = HTTP_STATUS_BY_EXCEPTION.get(type(exc), 422)
        return JSONResponse(
            status_code=status_code,
            content={"error": {"code": exc.code, "message": exc.message, "hint": exc.hint}},
        )

    @app.exception_handler(InvalidTrafficLightConfigError)
    async def handle_invalid_traffic_light_config(
        request: Request, exc: InvalidTrafficLightConfigError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "La configuración del semáforo no es válida.",
                    "hint": "Revisa config/traffic_light.yaml.",
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = uuid.uuid4().hex
        logger.exception("INTERNAL_ERROR request_id=%s", request_id)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Ha ocurrido un error inesperado.",
                    "hint": "Inténtalo de nuevo. Si persiste, contacta con soporte indicando el id.",
                    "request_id": request_id,
                }
            },
        )
