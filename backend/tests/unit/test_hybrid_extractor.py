"""Tests del extractor híbrido: cuándo usa el OCR tal cual y cuándo repite
la extracción con el respaldo de IA."""
from __future__ import annotations

from app.domain.errors import NoNutritionTableError
from app.domain.models import ExtractionResult, FieldStatus, NutritionField
from app.extraction.hybrid import HybridExtractor

OK_FIELD = NutritionField(value=1.0, unit="g", status=FieldStatus.OK, confidence=0.9)
DOUBTFUL_FIELD = NutritionField(value=1.0, unit="g", status=FieldStatus.DOUBTFUL, confidence=0.5)


class _StubExtractor:
    def __init__(self, result: ExtractionResult | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    def extract(self, content: bytes, mime_type: str) -> ExtractionResult:
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


def _full_ok_result() -> ExtractionResult:
    fields = {name: OK_FIELD for name in ("energy_kcal", "fat_g", "carbohydrates_g", "protein_g")}
    return ExtractionResult(basis="per_100g", fields=fields, extractor="tesseract-rules@1.0")


def _partial_result() -> ExtractionResult:
    fields = {
        "energy_kcal": OK_FIELD,
        "fat_g": DOUBTFUL_FIELD,
        "carbohydrates_g": OK_FIELD,
        "protein_g": OK_FIELD,
    }
    return ExtractionResult(basis="per_100g", fields=fields, extractor="tesseract-rules@1.0")


def test_uses_ocr_result_as_is_when_fully_ok() -> None:
    primary = _StubExtractor(result=_full_ok_result())
    fallback = _StubExtractor(result=_full_ok_result())

    result = HybridExtractor(primary=primary, fallback=fallback).extract(b"x", "image/jpeg")

    assert result.extractor == "tesseract-rules@1.0"
    assert result.warnings == []


def test_falls_back_to_ai_when_ocr_result_is_partial() -> None:
    fallback_result = _full_ok_result().__class__(
        basis="per_100g", fields=_full_ok_result().fields, extractor="claude-vision@1.0"
    )
    primary = _StubExtractor(result=_partial_result())
    fallback = _StubExtractor(result=fallback_result)

    result = HybridExtractor(primary=primary, fallback=fallback).extract(b"x", "image/jpeg")

    assert result.extractor == "claude-vision@1.0"
    assert any("IA" in warning for warning in result.warnings)


def test_degrades_to_partial_ocr_when_fallback_unavailable() -> None:
    primary = _StubExtractor(result=_partial_result())
    fallback = _StubExtractor(error=RuntimeError("sin API key"))

    result = HybridExtractor(primary=primary, fallback=fallback).extract(b"x", "image/jpeg")

    assert result.extractor == "tesseract-rules@1.0"
    assert any("respaldo de IA" in warning for warning in result.warnings)


def test_raises_original_ocr_error_when_nothing_is_usable_and_fallback_fails() -> None:
    primary_error = NoNutritionTableError(message="sin tabla", hint="encuadra mejor")
    primary = _StubExtractor(error=primary_error)
    fallback = _StubExtractor(error=RuntimeError("sin API key"))

    try:
        HybridExtractor(primary=primary, fallback=fallback).extract(b"x", "image/jpeg")
        assert False, "debía propagar el error original del OCR"
    except NoNutritionTableError:
        pass


def test_uses_ai_result_when_ocr_finds_nothing_and_fallback_works() -> None:
    primary_error = NoNutritionTableError(message="sin tabla", hint="encuadra mejor")
    fallback_result = _full_ok_result().__class__(
        basis="per_100g", fields=_full_ok_result().fields, extractor="claude-vision@1.0"
    )
    primary = _StubExtractor(error=primary_error)
    fallback = _StubExtractor(result=fallback_result)

    result = HybridExtractor(primary=primary, fallback=fallback).extract(b"x", "image/jpeg")

    assert result.extractor == "claude-vision@1.0"
    assert any("IA" in warning for warning in result.warnings)
