"""Esquemas Pydantic de salida y mapeo desde los modelos de dominio.

Solo serialización: estas funciones convierten dataclasses de dominio en
los modelos que FastAPI expone, sin tomar ninguna decisión de negocio.
"""
from __future__ import annotations

from pydantic import BaseModel

from app.domain.models import LabelAnalysisResult
from app.domain.traffic_light import TrafficLightRule


class NutritionFieldSchema(BaseModel):
    value: float | None
    unit: str
    status: str
    confidence: float
    raw_text: str | None
    source: str | None
    reason: str | None


class CheckResultSchema(BaseModel):
    name: str
    passed: bool
    detail: str


class LabelExtractionResponse(BaseModel):
    document_id: str
    basis: str
    fields: dict[str, NutritionFieldSchema]
    traffic_light: dict[str, str | None]
    checks: list[CheckResultSchema]
    warnings: list[str]
    extractor: str
    processing_ms: int


class TrafficLightRuleSchema(BaseModel):
    direction: str
    green_max: float | None = None
    red_min: float | None = None
    green_min: float | None = None
    red_max: float | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    hint: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


def to_response(result: LabelAnalysisResult) -> LabelExtractionResponse:
    return LabelExtractionResponse(
        document_id=result.document_id,
        basis=result.basis,
        fields={
            name: NutritionFieldSchema(
                value=field.value,
                unit=field.unit,
                status=field.status.value,
                confidence=field.confidence,
                raw_text=field.raw_text,
                source=field.source,
                reason=field.reason,
            )
            for name, field in result.fields.items()
        },
        traffic_light={
            name: color.value if color is not None else None for name, color in result.traffic_light.items()
        },
        checks=[CheckResultSchema(name=c.name, passed=c.passed, detail=c.detail) for c in result.checks],
        warnings=result.warnings,
        extractor=result.extractor,
        processing_ms=result.processing_ms,
    )


def traffic_light_rules_response(rules: dict[str, TrafficLightRule]) -> dict[str, TrafficLightRuleSchema]:
    return {
        name: TrafficLightRuleSchema(
            direction=rule.direction,
            green_max=rule.green_max,
            red_min=rule.red_min,
            green_min=rule.green_min,
            red_max=rule.red_max,
        )
        for name, rule in rules.items()
    }
