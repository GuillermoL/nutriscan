"""Extractor híbrido: OCR local primero, IA (Claude) como respaldo.

Compone dos Extractor sin saber nada de Tesseract ni de Anthropic en
concreto, solo del Protocol app.extraction.base.Extractor: se le inyectan
el extractor principal y el de respaldo por constructor.

Regla de negocio: si el OCR encuentra los cuatro campos sin dudas, se usa
tal cual (gratis, rápido, determinista). En cualquier otro caso —parcial,
con campos dudosos, o si el documento no da ni un campo— se repite la
extracción completa con IA sobre la misma foto y se usa ese resultado. Si
el respaldo de IA no está disponible (sin API key, sin red), se degrada al
resultado del OCR en vez de fallar la petición entera.
"""
from __future__ import annotations

from dataclasses import replace

from app.domain.errors import NoNutritionTableError, NoTextDetectedError
from app.domain.models import ExtractionResult, FieldStatus
from app.extraction.base import Extractor

NAME = "hybrid@1.0"

_FALLBACK_USED_WARNING = (
    "El OCR local no encontró todos los campos con confianza; se ha completado "
    "el análisis con IA sobre la misma foto."
)
_FALLBACK_DEGRADED_WARNING = (
    "El OCR local no encontró todos los campos con confianza y el respaldo de IA "
    "no estaba disponible; se muestra el resultado parcial del OCR."
)


def _is_fully_ok(result: ExtractionResult) -> bool:
    return all(nutrition_field.status == FieldStatus.OK for nutrition_field in result.fields.values())


def _with_warning(result: ExtractionResult, warning: str) -> ExtractionResult:
    return replace(result, warnings=[*result.warnings, warning])


class HybridExtractor:
    name = NAME

    def __init__(self, primary: Extractor, fallback: Extractor) -> None:
        self._primary = primary
        self._fallback = fallback

    def extract(self, content: bytes, mime_type: str) -> ExtractionResult:
        try:
            primary_result = self._primary.extract(content, mime_type)
        except (NoTextDetectedError, NoNutritionTableError) as primary_error:
            try:
                fallback_result = self._fallback.extract(content, mime_type)
            except Exception:
                # Sin nada del OCR y sin respaldo de IA: el error original del
                # OCR (NO_TEXT_DETECTED / NO_NUTRITION_TABLE) es el que tiene
                # un hint útil para el usuario.
                raise primary_error from None
            return _with_warning(fallback_result, _FALLBACK_USED_WARNING)

        if _is_fully_ok(primary_result):
            return primary_result

        try:
            fallback_result = self._fallback.extract(content, mime_type)
        except Exception:
            return _with_warning(primary_result, _FALLBACK_DEGRADED_WARNING)

        return _with_warning(fallback_result, _FALLBACK_USED_WARNING)
