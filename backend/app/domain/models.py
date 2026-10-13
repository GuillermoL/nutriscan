"""Modelos de dominio del resultado de extracción.

Dataclasses puras: nada de aquí importa FastAPI, Pydantic ni el motor de
OCR, para que el dominio se pueda testear y razonar sin esas dependencias.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

NUTRITION_FIELD_NAMES = ("energy_kcal", "fat_g", "carbohydrates_g", "protein_g")


class FieldStatus(str, Enum):
    OK = "ok"
    DOUBTFUL = "doubtful"
    NOT_FOUND = "not_found"


class TrafficLightColor(str, Enum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


@dataclass(frozen=True)
class NutritionField:
    value: float | None
    unit: str
    status: FieldStatus
    confidence: float
    raw_text: str | None = None
    source: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ExtractionResult:
    """Salida cruda de un Extractor: solo lo que el OCR/parser puede saber."""

    basis: str
    fields: dict[str, NutritionField]
    checks: list[CheckResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    extractor: str = ""


@dataclass(frozen=True)
class LabelAnalysisResult:
    """Resultado final tras añadir el semáforo: lo que devuelve la API."""

    document_id: str
    basis: str
    fields: dict[str, NutritionField]
    traffic_light: dict[str, TrafficLightColor | None]
    overall_traffic_light: TrafficLightColor | None
    checks: list[CheckResult]
    warnings: list[str]
    extractor: str
    processing_ms: int
