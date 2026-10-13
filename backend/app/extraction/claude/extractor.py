"""Extractor con IA (Claude, visión), usado como respaldo cuando el OCR local
no es fiable.

Es el único módulo que conoce el SDK de Anthropic; el resto de la app solo
ve app.extraction.base.Extractor, igual que con Tesseract. Tras leer los
cuatro campos de la foto se reutilizan los mismos validadores de dominio
(rango plausible, Atwater, kJ/kcal) que usa el extractor OCR, para que el
criterio de "dudoso" sea idéntico sin importar el origen de los datos.
"""
from __future__ import annotations

import base64
import json
import os

import anthropic

from app.domain.models import ExtractionResult, FieldStatus, NutritionField
from app.domain.nutrition_checks import apply_check_results, run_checks
from app.domain.validators import is_in_range
from app.extraction.magic_bytes import detect_mime_type

EXTRACTOR_NAME = "claude-vision@1.0"
DEFAULT_MODEL = "claude-opus-5"
BASE_CONFIDENCE = 0.75
MAX_TOKENS = 1024

FIELD_UNITS = {
    "energy_kcal": "kcal",
    "fat_g": "g",
    "carbohydrates_g": "g",
    "protein_g": "g",
}

PROMPT = (
    "Eres un extractor de datos, no un asistente conversacional. Mira la imagen "
    "de una etiqueta de información nutricional de un alimento (puede estar en "
    "español, inglés u otro idioma) y extrae, por 100 g o 100 ml de producto "
    "(no por ración individual si ambas columnas existen), estos cuatro valores:\n\n"
    "- energy_kcal: energía en kilocalorías. Si la etiqueta solo da kJ, "
    "conviértelo a kcal (kcal = kJ / 4.184) y dilo en raw_text.\n"
    "- fat_g: grasas totales en gramos (NO la grasa saturada).\n"
    "- carbohydrates_g: hidratos de carbono / carbohidratos totales en gramos "
    "(NO los azúcares).\n"
    "- protein_g: proteínas en gramos.\n\n"
    "Para cada campo indica si lo encontraste (found), su valor numérico "
    "(value, null si no lo encontraste) y el texto literal de la etiqueta del "
    "que lo sacaste (raw_text, null si no lo encontraste). Si la imagen no es "
    "una etiqueta nutricional o no contiene estos datos, devuelve found=false "
    "en los cuatro campos."
)

_FIELD_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "value": {"anyOf": [{"type": "number"}, {"type": "null"}]},
        "raw_text": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    },
    "required": ["found", "value", "raw_text"],
    "additionalProperties": False,
}

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "object",
            "properties": {name: _FIELD_SCHEMA for name in FIELD_UNITS},
            "required": list(FIELD_UNITS),
            "additionalProperties": False,
        }
    },
    "required": ["fields"],
    "additionalProperties": False,
}


class ClaudeExtractionError(RuntimeError):
    """La llamada a la API de Claude ha fallado o no se pudo interpretar."""


def _build_field(name: str, raw: dict) -> NutritionField:
    if not raw.get("found") or raw.get("value") is None:
        return NutritionField(
            value=None,
            unit=FIELD_UNITS[name],
            status=FieldStatus.NOT_FOUND,
            confidence=0.0,
            raw_text=None,
            source=None,
            reason="No se encontró en la imagen (IA)",
        )

    value = float(raw["value"])
    confidence = BASE_CONFIDENCE
    status = FieldStatus.OK
    reason = None
    if not is_in_range(name, value):
        confidence *= 0.5
        status = FieldStatus.DOUBTFUL
        reason = "Valor fuera de rango plausible"

    return NutritionField(
        value=value,
        unit=FIELD_UNITS[name],
        status=status,
        confidence=round(confidence, 2),
        raw_text=raw.get("raw_text"),
        source="claude-vision",
        reason=reason,
    )


class ClaudeExtractor:
    name = EXTRACTOR_NAME

    def __init__(self, model: str | None = None) -> None:
        # CLAUDE_MODEL permite abaratar el respaldo (p. ej. a un Sonnet) sin
        # tocar código; por defecto se usa el modelo más capaz disponible.
        self.model = model or os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)

    def extract(self, content: bytes, mime_type: str) -> ExtractionResult:
        del mime_type  # el tipo real ya se detecta por magic bytes, no nos fiamos del declarado
        detected_mime = detect_mime_type(content)
        encoded = base64.standard_b64encode(content).decode("ascii")

        if detected_mime == "application/pdf":
            document_block = {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": encoded},
            }
        else:
            document_block = {
                "type": "image",
                "source": {"type": "base64", "media_type": detected_mime, "data": encoded},
            }

        try:
            # El cliente se construye aquí, no en __init__: así una
            # ANTHROPIC_API_KEY ausente falla solo cuando de verdad se
            # necesita el respaldo de IA, no en cada petición.
            client = anthropic.Anthropic()
            response = client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
                messages=[{"role": "user", "content": [document_block, {"type": "text", "text": PROMPT}]}],
            )
            if response.stop_reason == "refusal":
                raise ClaudeExtractionError("Claude ha rechazado la petición (refusal).")

            text_block = next((block for block in response.content if block.type == "text"), None)
            if text_block is None:
                raise ClaudeExtractionError("La respuesta de Claude no contiene el JSON esperado.")

            raw_fields = json.loads(text_block.text)["fields"]
            fields = {name: _build_field(name, raw_fields[name]) for name in FIELD_UNITS}
        except ClaudeExtractionError:
            raise
        except Exception as exc:
            raise ClaudeExtractionError(f"No se pudo completar la extracción con IA: {exc}") from exc

        checks = run_checks(fields)
        fields = apply_check_results(fields, checks)

        return ExtractionResult(
            basis="per_100g",
            fields=fields,
            checks=checks,
            warnings=[],
            extractor=self.name,
        )
