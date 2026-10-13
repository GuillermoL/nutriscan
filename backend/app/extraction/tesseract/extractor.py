"""Compone carga + preprocesado + OCR + parseo + validación en un Extractor.

Es el único módulo que conoce a la vez Tesseract, OpenCV y PyMuPDF; el
resto de la app solo ve app.extraction.base.Extractor.
"""
from __future__ import annotations

import io

import cv2
import fitz
import numpy as np
from PIL import Image, ImageOps

from app.domain.errors import CorruptFileError, NoNutritionTableError, NoTextDetectedError
from app.domain.models import ExtractionResult, FieldStatus, NutritionField
from app.domain.nutrition_checks import apply_check_results, run_checks
from app.domain.validators import is_in_range
from app.extraction.magic_bytes import detect_mime_type
from app.extraction.tesseract import ocr as ocr_module
from app.extraction.tesseract.parser import ParsedField, parse_label_text
from app.extraction.tesseract.preprocess import PreprocessResult, preprocess_image

EXTRACTOR_NAME = "tesseract-rules@1.0"
MIN_TEXT_CHARS = 20
# psm 11 (texto disperso) se probó contra el banco de samples/ reales y no
# encontró ni un solo campo en ningún caso: solo añadía latencia.
PSM_ATTEMPTS = ("6", "4")
MIN_FIELDS_TO_STOP_RETRYING = 2
PDF_RENDER_DPI = 300


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
        checks = run_checks(fields)
        fields = apply_check_results(fields, checks)

        return ExtractionResult(
            basis="per_100g",
            fields=fields,
            checks=checks,
            warnings=warnings,
            extractor=self.name,
        )
