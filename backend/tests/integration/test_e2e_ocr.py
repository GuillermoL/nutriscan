"""Test end-to-end con fotos reales de samples/.

Se salta si no hay Tesseract instalado, o si samples/expected.json todavía
no tiene entradas (el usuario añade las fotos a mano, ver samples/README.md).

El umbral global (ver samples/README.md) sale de medir el banco real: 9/32
campos (28%) con 8 fotos deliberadamente difíciles (baja resolución, fondos
ilustrados). No se exige un mínimo por foto individual porque una etiqueta
difícil que falla honestamente (not_found / NO_NUTRITION_TABLE) es el
comportamiento correcto, no una regresión; lo que importa es que el acierto
agregado no se hunda respecto a lo medido.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "samples"
EXPECTED_PATH = SAMPLES_DIR / "expected.json"
MIN_OVERALL_ACCURACY = 0.20  # medido 28% sobre el banco actual; margen para variación del motor OCR
NUMERIC_TOLERANCE = 0.05  # 5% relativo


def _tesseract_available() -> bool:
    if shutil.which("tesseract") is not None:
        return True
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _load_expected() -> dict[str, dict[str, float]]:
    if not EXPECTED_PATH.exists():
        return {}
    data = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    return {name: fields for name, fields in data.items() if (SAMPLES_DIR / name).exists()}


pytestmark = pytest.mark.ocr

_expected = _load_expected()

if not _tesseract_available():
    pytest.skip("Tesseract no está instalado", allow_module_level=True)
if not _expected:
    pytest.skip(
        "No hay fotos en samples/ con entradas en expected.json todavía (ver samples/README.md)",
        allow_module_level=True,
    )


def _values_match(actual: float | None, expected: float, tolerance: float = NUMERIC_TOLERANCE) -> bool:
    if actual is None:
        return False
    if expected == 0:
        return actual == 0
    return abs(actual - expected) / abs(expected) <= tolerance


def _extract(filename: str):
    """None si el extractor rechaza la foto con un error de dominio conocido
    (NO_TEXT_DETECTED, NO_NUTRITION_TABLE...): eso es un fallo honesto ante
    una foto difícil, no un crash del pipeline."""
    from app.domain.errors import LabelExtractionError
    from app.extraction.tesseract.extractor import TesseractExtractor

    image_path = SAMPLES_DIR / filename
    content = image_path.read_bytes()
    mime_type = "application/pdf" if image_path.suffix.lower() == ".pdf" else "image/jpeg"
    try:
        return TesseractExtractor().extract(content, mime_type)
    except LabelExtractionError:
        return None


@pytest.mark.parametrize("filename", sorted(_expected.keys()))
def test_sample_extraction_does_not_crash(filename: str) -> None:
    """Smoke test por foto: o bien devuelve los cuatro campos, o bien el
    extractor rechaza la foto con un error de dominio conocido; nunca una
    excepción inesperada."""
    result = _extract(filename)
    if result is not None:
        assert set(result.fields.keys()) == {"energy_kcal", "fat_g", "carbohydrates_g", "protein_g"}


def test_overall_accuracy_meets_measured_floor() -> None:
    total_fields = 0
    total_matches = 0
    per_sample: dict[str, str] = {}

    for filename, expected_fields in _expected.items():
        result = _extract(filename)
        matches = 0
        for field_name, expected_value in expected_fields.items():
            total_fields += 1
            actual_value = result.fields[field_name].value if result is not None else None
            if _values_match(actual_value, expected_value):
                total_matches += 1
                matches += 1
        per_sample[filename] = f"{matches}/{len(expected_fields)}"

    accuracy = total_matches / total_fields if total_fields else 0.0
    print(f"\nAcierto por foto: {per_sample}")
    print(f"Acierto global sobre samples/: {total_matches}/{total_fields} ({accuracy:.0%})")

    assert accuracy >= MIN_OVERALL_ACCURACY, (
        f"Acierto global {accuracy:.0%} por debajo del suelo medido ({MIN_OVERALL_ACCURACY:.0%}). "
        f"Por foto: {per_sample}"
    )
