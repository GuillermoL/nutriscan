"""Endpoints de etiquetas. Validan la entrada y serializan la salida del
servicio; no decide nada sobre extracción ni sobre el semáforo."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.schemas import LabelExtractionResponse, TrafficLightRuleSchema, to_response, traffic_light_rules_response
from app.core.config import Settings, get_settings, get_traffic_light_rules
from app.domain.errors import FileTooLargeError
from app.domain.traffic_light import TrafficLightRule
from app.extraction.base import Extractor
from app.extraction.factory import build_extractor
from app.services.label_analysis import analyze_label

router = APIRouter(prefix="/api/v1", tags=["labels"])


def get_extractor(settings: Settings = Depends(get_settings)) -> Extractor:
    return build_extractor(settings.extractor)


def get_rules(_: Settings = Depends(get_settings)) -> dict[str, TrafficLightRule]:
    return get_traffic_light_rules()


@router.post("/labels/extract", response_model=LabelExtractionResponse)
async def extract_label(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    extractor: Extractor = Depends(get_extractor),
    traffic_light_rules: dict[str, TrafficLightRule] = Depends(get_rules),
) -> LabelExtractionResponse:
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise FileTooLargeError(
            message=f"El archivo supera el límite de {settings.max_upload_mb} MB.",
            hint="Comprime la imagen o reduce la resolución antes de subirla.",
        )

    result = analyze_label(
        content=content,
        mime_type=file.content_type or "application/octet-stream",
        extractor=extractor,
        traffic_light_rules=traffic_light_rules,
    )
    return to_response(result)


@router.get("/traffic-light/config")
async def get_traffic_light_config(
    traffic_light_rules: dict[str, TrafficLightRule] = Depends(get_rules),
) -> dict[str, TrafficLightRuleSchema]:
    return traffic_light_rules_response(traffic_light_rules)
