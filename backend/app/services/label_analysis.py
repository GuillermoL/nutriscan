"""Orquesta el extractor configurado y el semáforo de dominio.

No contiene reglas de negocio propias: delega la extracción en el
Extractor inyectado y la clasificación en app.domain.traffic_light.
"""
from __future__ import annotations

import time
import uuid

from app.domain.models import FieldStatus, LabelAnalysisResult, TrafficLightColor
from app.domain.traffic_light import TrafficLightRule, classify_value
from app.extraction.base import Extractor


def analyze_label(
    content: bytes,
    mime_type: str,
    extractor: Extractor,
    traffic_light_rules: dict[str, TrafficLightRule],
) -> LabelAnalysisResult:
    started = time.perf_counter()
    extraction = extractor.extract(content, mime_type)
    elapsed_ms = round((time.perf_counter() - started) * 1000)

    traffic_light: dict[str, TrafficLightColor | None] = {}
    for name, nutrition_field in extraction.fields.items():
        if nutrition_field.status == FieldStatus.NOT_FOUND or nutrition_field.value is None:
            traffic_light[name] = None
        else:
            traffic_light[name] = classify_value(nutrition_field.value, traffic_light_rules[name])

    return LabelAnalysisResult(
        document_id=uuid.uuid4().hex,
        basis=extraction.basis,
        fields=extraction.fields,
        traffic_light=traffic_light,
        checks=extraction.checks,
        warnings=extraction.warnings,
        extractor=extraction.extractor,
        processing_ms=elapsed_ms,
    )
