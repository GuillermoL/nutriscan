"""OCR vía pytesseract: imagen preprocesada → texto plano con confianza.

Solo conoce Tesseract. No decide reintentos de PSM ni interpreta el texto;
eso es responsabilidad de extractor.py y parser.py respectivamente.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytesseract

from app.domain.errors import OcrEngineUnavailableError

DEFAULT_LANG = "spa+eng"


@dataclass(frozen=True)
class OcrResult:
    text: str
    mean_confidence: float  # 0-100, media de las confianzas de palabra de Tesseract


def _lines_in_reading_order(data: dict) -> list[str]:
    lines: dict[tuple[int, int, int], list[str]] = {}
    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(word)
    return [" ".join(words) for words in lines.values()]


def run_ocr(image: np.ndarray, psm: str, lang: str = DEFAULT_LANG) -> OcrResult:
    try:
        data = pytesseract.image_to_data(
            image, lang=lang, config=f"--psm {psm}", output_type=pytesseract.Output.DICT
        )
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrEngineUnavailableError(
            message="El motor de OCR no está disponible en el servidor.",
            hint="Instala Tesseract o usa la imagen Docker del proyecto, que ya lo incluye.",
        ) from exc

    confidences = [float(c) for c in data["conf"] if str(c) not in ("-1", "")]
    mean_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    text = "\n".join(_lines_in_reading_order(data))
    return OcrResult(text=text, mean_confidence=mean_confidence)
