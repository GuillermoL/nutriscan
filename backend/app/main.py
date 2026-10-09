"""Punto de entrada de la API: crea FastAPI, CORS, routers y handlers.

Los umbrales del semáforo se validan aquí, al importar el módulo: si el
YAML es inválido, la app no arranca y el motivo queda en el traceback.
"""
from __future__ import annotations

import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_exception_handlers
from app.api.routes_labels import router as labels_router
from app.core.config import Settings, get_settings, get_traffic_light_rules
from app.domain.traffic_light import InvalidTrafficLightConfigError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nutriscan")

try:
    get_traffic_light_rules()
except InvalidTrafficLightConfigError as exc:
    logger.error("Umbrales de semáforo inválidos, la app no arranca: %s", exc)
    raise

app = FastAPI(title="NutriScan API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(labels_router)


@app.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict:
    status: dict = {"status": "ok", "extractor": settings.extractor}
    if settings.extractor == "tesseract":
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
        except Exception:
            status["status"] = "degraded"
            status["detail"] = "OCR_ENGINE_UNAVAILABLE"
    return status
