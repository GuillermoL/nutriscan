"""Compone carga + preprocesado + OCR + parseo + validación en un Extractor.

Es el único módulo que conoce a la vez Tesseract, OpenCV y PyMuPDF; el
resto de la app solo ve app.extraction.base.Extractor.
"""
from __future__ import annotations

import io
import re
from dataclasses import replace

import cv2
import fitz
import numpy as np
from PIL import Image, ImageOps

from app.domain.errors import CorruptFileError, NoNutritionTableError, NoTextDetectedError, UnsupportedFormatError
from app.domain.models import CheckResult, ExtractionResult, FieldStatus, NutritionField
from app.extraction.tesseract import ocr as ocr_module
from app.extraction.tesseract.parser import ParsedField, parse_label_text
from app.extraction.tesseract.preprocess import PreprocessResult, preprocess_image
from app.extraction.tesseract.validators import (
    atwater_consistent,
    is_in_range,
    kj_kcal_consistent,
    macro_sum_valid,
)

EXTRACTOR_NAME = "tesseract-rules@1.0"
MIN_TEXT_CHARS = 20
# psm 11 (texto disperso) se probó contra el banco de samples/ reales y no
# encontró ni un solo campo en ningún caso: solo añadía latencia.
PSM_ATTEMPTS = ("6", "4")
MIN_FIELDS_TO_STOP_RETRYING = 2
PDF_RENDER_DPI = 300

_KJ_PATTERN = re.compile(r"(\d{1,4}(?:[.,]\d{1,2})?)\s*kj")


def detect_mime_type(content: bytes) -> str:
    """Identifica el formato real por magic bytes; nunca por la extensión."""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"%PDF"):
        return "application/pdf"
    raise UnsupportedFormatError(
        message="El tipo de archivo no está admitido.",
        hint="Sube una foto en JPG, PNG o WEBP, o un PDF.",
    )


def _load_image(content: bytes) -> np.ndarray:
    try:
        pil_image = ImageOps.exif_transpose(Image.open(io.BytesIO(content)))
        rgb_array = np.array(pil_image.convert("RGB"))
    except Exception as exc:  # Pillow lanza distintos tipos según el fallo concreto
        raise CorruptFileError(
            message="El archivo de imagen está dañado o no se puede leer.",
            hint="Vuelve a hacer la foto o exporta de nuevo el archivo.",
        ) from exc
    return cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)


def _load_pdf(content: bytes) -> tuple[str | None, np.ndarray | None]:
    try:
        document = fitz.open(stream=content, filetype="pdf")
        if document.page_count == 0:
            raise CorruptFileError(
                message="El PDF no contiene páginas.",
                hint="Comprueba el archivo y vuelve a intentarlo.",
            )
        page = document[0]
        text = page.get_text().strip()
        if len(text) >= MIN_TEXT_CHARS:
            return text, None

        pixmap = page.get_pixmap(dpi=PDF_RENDER_DPI)
        raw = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)
        color_conversion = cv2.COLOR_RGBA2BGR if pixmap.n == 4 else cv2.COLOR_RGB2BGR
        return None, cv2.cvtColor(raw, color_conversion)
    except CorruptFileError:
        raise
    except Exception as exc:
        raise CorruptFileError(
            message="El PDF está dañado o no se puede leer.",
            hint="Vuelve a exportar el PDF y vuelve a intentarlo.",
        ) from exc


def _count_found_fields(parsed_fields: dict[str, ParsedField]) -> int:
    return sum(1 for parsed in parsed_fields.values() if parsed.value is not None)


def _ocr_with_psm_retries(
    preprocessed: PreprocessResult, languages: str
) -> tuple[ocr_module.OcrResult, dict[str, ParsedField]]:
    """Prueba cada variante de imagen con cada PSM y se queda con la mejor.

    Sobre fotos reales ninguna de las tres variantes gana siempre (ver
    PreprocessResult), así que probamos las tres y nos quedamos con la que
    encuentre más campos; en empate, con la de mayor confianza media de
    Tesseract. Es más lento que apostar por una sola combinación, pero en
    un endpoint de subida de una foto a la vez el coste es aceptable.
    """
    best: tuple[ocr_module.OcrResult, dict[str, ParsedField]] | None = None
    best_count = -1
    best_confidence = -1.0
    for image in (preprocessed.plain_gray, preprocessed.enhanced_gray, preprocessed.binary):
        for psm in PSM_ATTEMPTS:
            result = ocr_module.run_ocr(image, psm=psm, lang=languages)
            parsed_fields = parse_label_text(result.text)
            count = _count_found_fields(parsed_fields)
            if count > best_count or (count == best_count and result.mean_confidence > best_confidence):
                best = (result, parsed_fields)
                best_count = count
                best_confidence = result.mean_confidence
            if count >= MIN_FIELDS_TO_STOP_RETRYING:
                return best
    assert best is not None  # siempre hay al menos un intento
    return best


def _extract_kj_from_raw(raw_text: str | None) -> float | None:
    if not raw_text:
        return None
    match = _KJ_PATTERN.search(raw_text.lower())
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _map_source(parsed_source: str | None, origin: str) -> str | None:
    if parsed_source is None or origin != "pdf_text":
        return parsed_source
    return "pdf_text_kj_converted" if parsed_source == "ocr_kj_converted" else "pdf_text"


def _build_fields(
    parsed_fields: dict[str, ParsedField], base_confidence: float, origin: str
) -> dict[str, NutritionField]:
    fields: dict[str, NutritionField] = {}
    for name, parsed in parsed_fields.items():
        if parsed.value is None:
            fields[name] = NutritionField(
                value=None,
                unit=parsed.unit,
                status=FieldStatus.NOT_FOUND,
                confidence=0.0,
                raw_text=None,
                source=None,
                reason=parsed.reason,
            )
            continue

        confidence = base_confidence
        status = FieldStatus.OK
        reason = parsed.reason
        if parsed.reason:
            confidence *= 0.85
            status = FieldStatus.DOUBTFUL
        if not is_in_range(name, parsed.value):
            confidence *= 0.5
            status = FieldStatus.DOUBTFUL
            reason = f"{reason}; Valor fuera de rango plausible" if reason else "Valor fuera de rango plausible"

        fields[name] = NutritionField(
            value=parsed.value,
            unit=parsed.unit,
            status=status,
            confidence=round(min(confidence, 1.0), 2),
            raw_text=parsed.raw_text,
            source=_map_source(parsed.source, origin),
            reason=reason,
        )
    return fields


def _downgrade(nutrition_field: NutritionField, reason: str) -> NutritionField:
    if nutrition_field.status == FieldStatus.NOT_FOUND:
        return nutrition_field
    combined_reason = f"{nutrition_field.reason}; {reason}" if nutrition_field.reason else reason
    return replace(
        nutrition_field,
        status=FieldStatus.DOUBTFUL,
        confidence=round(nutrition_field.confidence * 0.7, 2),
        reason=combined_reason,
    )


def _run_checks(fields: dict[str, NutritionField]) -> list[CheckResult]:
    checks: list[CheckResult] = []
    energy, fat, carbs, protein = (
        fields["energy_kcal"],
        fields["fat_g"],
        fields["carbohydrates_g"],
        fields["protein_g"],
    )

    kj_value = _extract_kj_from_raw(energy.raw_text) if energy.value is not None else None
    if kj_value is not None:
        passed = kj_kcal_consistent(kj_value, energy.value)
        checks.append(
            CheckResult(
                name="kj_kcal_consistency",
                passed=passed,
                detail=f"{kj_value:g} kJ declarados vs {energy.value:g} kcal declaradas",
            )
        )

    macros = {"fat_g": fat.value, "carbohydrates_g": carbs.value, "protein_g": protein.value}
    missing = [name for name, value in macros.items() if value is None]
    if energy.value is None:
        missing = ["energy_kcal", *missing]
    if missing:
        checks.append(
            CheckResult(
                name="atwater_energy",
                passed=False,
                detail=f"No evaluable: falta(n) {', '.join(missing)}",
            )
        )
    else:
        expected_kcal = 9 * fat.value + 4 * carbs.value + 4 * protein.value
        passed = atwater_consistent(energy.value, fat.value, carbs.value, protein.value)
        checks.append(
            CheckResult(
                name="atwater_energy",
                passed=passed,
                detail=f"{energy.value:g} kcal declaradas vs {expected_kcal:g} calculadas (Atwater)",
            )
        )

    if not missing:
        passed = macro_sum_valid(fat.value, carbs.value, protein.value)
        checks.append(
            CheckResult(
                name="macro_sum",
                passed=passed,
                detail=f"Suma de macronutrientes: {fat.value + carbs.value + protein.value:g} g por 100 g",
            )
        )

    return checks


def _apply_check_results(
    fields: dict[str, NutritionField], checks: list[CheckResult]
) -> dict[str, NutritionField]:
    updated = dict(fields)
    by_name = {check.name: check for check in checks}

    kj_check = by_name.get("kj_kcal_consistency")
    if kj_check and not kj_check.passed:
        updated["energy_kcal"] = _downgrade(updated["energy_kcal"], "Incoherencia kJ/kcal")

    atwater_check = by_name.get("atwater_energy")
    if atwater_check and not atwater_check.passed and not atwater_check.detail.startswith("No evaluable"):
        for name in ("energy_kcal", "fat_g", "carbohydrates_g", "protein_g"):
            updated[name] = _downgrade(updated[name], "Incoherencia con el cálculo de Atwater")

    macro_check = by_name.get("macro_sum")
    if macro_check and not macro_check.passed:
        for name in ("fat_g", "carbohydrates_g", "protein_g"):
            updated[name] = _downgrade(updated[name], "Suma de macronutrientes superior a 100 g")

    return updated


class TesseractExtractor:
    name = EXTRACTOR_NAME

    def __init__(self, languages: str = ocr_module.DEFAULT_LANG) -> None:
        self.languages = languages

    def extract(self, content: bytes, mime_type: str) -> ExtractionResult:
        del mime_type  # el tipo real ya se detecta por magic bytes, no nos fiamos del declarado
        detected_mime = detect_mime_type(content)
        warnings: list[str] = []

        if detected_mime == "application/pdf":
            pdf_text, page_image = _load_pdf(content)
        else:
            pdf_text, page_image = None, _load_image(content)

        if pdf_text is not None:
            parsed_fields = parse_label_text(pdf_text)
            base_confidence = 1.0
            origin = "pdf_text"
        else:
            preprocessed = preprocess_image(page_image)
            warnings.extend(preprocessed.warnings)
            ocr_result, parsed_fields = _ocr_with_psm_retries(preprocessed, self.languages)
            if len(ocr_result.text.strip()) < MIN_TEXT_CHARS:
                raise NoTextDetectedError(
                    message="No se ha podido leer texto en la imagen.",
                    hint="Repite la foto con mejor luz, más enfoque y sin reflejos.",
                )
            base_confidence = ocr_result.mean_confidence / 100
            origin = "ocr"

        if _count_found_fields(parsed_fields) == 0:
            raise NoNutritionTableError(
                message="No se ha encontrado una tabla nutricional en el documento.",
                hint="Encuadra solo la tabla de información nutricional, con buena luz y sin reflejos.",
            )

        fields = _build_fields(parsed_fields, base_confidence, origin)
        checks = _run_checks(fields)
        fields = _apply_check_results(fields, checks)

        return ExtractionResult(
            basis="per_100g",
            fields=fields,
            checks=checks,
            warnings=warnings,
            extractor=self.name,
        )
