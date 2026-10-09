"""Tests de integración del endpoint, con un Extractor falso inyectado.

No tocan Tesseract ni OpenCV: solo verifican que la API traduce
correctamente los resultados y errores de dominio a HTTP.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes_labels import get_extractor, get_rules
from app.core.config import Settings, get_settings
from app.domain.errors import (
    CorruptFileError,
    NoNutritionTableError,
    NoTextDetectedError,
    UnsupportedFormatError,
)
from app.domain.models import ExtractionResult, FieldStatus, NutritionField
from app.domain.traffic_light import TrafficLightRule
from app.main import app

TEST_RULES = {
    "energy_kcal": TrafficLightRule(direction="lower_is_better", green_max=150, red_min=400),
    "fat_g": TrafficLightRule(direction="lower_is_better", green_max=3.0, red_min=17.5),
    "carbohydrates_g": TrafficLightRule(direction="lower_is_better", green_max=15.0, red_min=45.0),
    "protein_g": TrafficLightRule(direction="higher_is_better", green_min=10.0, red_max=3.0),
}

FULL_FIELDS = {
    "energy_kcal": NutritionField(
        value=452, unit="kcal", status=FieldStatus.OK, confidence=0.91, raw_text="452 kcal", source="ocr"
    ),
    "fat_g": NutritionField(
        value=21.0, unit="g", status=FieldStatus.OK, confidence=0.88, raw_text="Grasas 21 g", source="ocr"
    ),
    "carbohydrates_g": NutritionField(
        value=58.0, unit="g", status=FieldStatus.OK, confidence=0.9, raw_text="Hidratos 58 g", source="ocr"
    ),
    "protein_g": NutritionField(
        value=6.0, unit="g", status=FieldStatus.OK, confidence=0.9, raw_text="Proteinas 6 g", source="ocr"
    ),
}

PARTIAL_FIELDS = {
    **{name: field for name, field in FULL_FIELDS.items() if name != "protein_g"},
    "protein_g": NutritionField(
        value=None, unit="g", status=FieldStatus.NOT_FOUND, confidence=0.0, reason="No se encontró la palabra clave"
    ),
}


class FakeExtractor:
    name = "fake@1.0"

    def __init__(self, result: ExtractionResult | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    def extract(self, content: bytes, mime_type: str) -> ExtractionResult:
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


@pytest.fixture
def client():
    app.dependency_overrides[get_rules] = lambda: TEST_RULES
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_rules, None)
    app.dependency_overrides.pop(get_extractor, None)
    app.dependency_overrides.pop(get_settings, None)


def _inject_extractor(result: ExtractionResult | None = None, error: Exception | None = None) -> None:
    app.dependency_overrides[get_extractor] = lambda: FakeExtractor(result=result, error=error)


def _post_label(client: TestClient, content: bytes = b"fake-bytes", content_type: str = "image/jpeg"):
    return client.post("/api/v1/labels/extract", files={"file": ("label.jpg", content, content_type)})


def test_extract_returns_200_with_all_fields_ok(client: TestClient) -> None:
    _inject_extractor(
        result=ExtractionResult(basis="per_100g", fields=FULL_FIELDS, checks=[], warnings=[], extractor="fake@1.0")
    )

    response = _post_label(client)

    assert response.status_code == 200
    body = response.json()
    assert body["fields"]["protein_g"]["status"] == "ok"
    assert body["traffic_light"]["fat_g"] == "red"
    assert body["traffic_light"]["protein_g"] == "amber"
    assert body["extractor"] == "fake@1.0"


def test_extract_returns_200_partial_when_one_field_is_missing(client: TestClient) -> None:
    _inject_extractor(
        result=ExtractionResult(basis="per_100g", fields=PARTIAL_FIELDS, checks=[], warnings=[], extractor="fake@1.0")
    )

    response = _post_label(client)

    assert response.status_code == 200
    body = response.json()
    assert body["fields"]["protein_g"]["status"] == "not_found"
    assert body["traffic_light"]["protein_g"] is None
    assert body["fields"]["fat_g"]["status"] == "ok"


def test_extract_returns_415_for_unsupported_format(client: TestClient) -> None:
    _inject_extractor(error=UnsupportedFormatError(message="Formato no admitido.", hint="Usa JPG, PNG o PDF."))

    response = _post_label(client, content=b"hola", content_type="text/plain")

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_FORMAT"


def test_extract_returns_413_when_file_too_large(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(max_upload_mb=0)
    _inject_extractor(
        result=ExtractionResult(basis="per_100g", fields=FULL_FIELDS, checks=[], warnings=[], extractor="fake@1.0")
    )

    response = _post_label(client, content=b"x" * 1024)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


@pytest.mark.parametrize(
    "error, expected_code",
    [
        (CorruptFileError(message="x", hint="y"), "CORRUPT_FILE"),
        (NoTextDetectedError(message="x", hint="y"), "NO_TEXT_DETECTED"),
        (NoNutritionTableError(message="x", hint="y"), "NO_NUTRITION_TABLE"),
    ],
)
def test_extract_returns_422_for_known_extraction_failures(
    client: TestClient, error: Exception, expected_code: str
) -> None:
    _inject_extractor(error=error)

    response = _post_label(client)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == expected_code


def test_health_endpoint_is_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
