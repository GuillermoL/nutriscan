"""Excepciones de dominio para fallos esperados de la extracción.

Cada una lleva un código estable, un mensaje para el usuario y una pista.
La capa api/errors.py las traduce a la respuesta HTTP y el JSON de error;
el dominio y la extracción no saben nada de FastAPI ni de códigos HTTP.
"""
from __future__ import annotations


class LabelExtractionError(Exception):
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class UnsupportedFormatError(LabelExtractionError):
    code = "UNSUPPORTED_FORMAT"


class FileTooLargeError(LabelExtractionError):
    code = "FILE_TOO_LARGE"


class CorruptFileError(LabelExtractionError):
    code = "CORRUPT_FILE"


class NoTextDetectedError(LabelExtractionError):
    code = "NO_TEXT_DETECTED"


class NoNutritionTableError(LabelExtractionError):
    code = "NO_NUTRITION_TABLE"


class OcrEngineUnavailableError(LabelExtractionError):
    code = "OCR_ENGINE_UNAVAILABLE"
