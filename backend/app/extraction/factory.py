"""Elige el extractor de etiquetas según la variable de entorno EXTRACTOR.

Sustituir Tesseract por otro motor (p. ej. un extractor basado en LLM) es
añadir una rama aquí: la API, el servicio y el frontend no cambian porque
ambos cumplen el mismo Protocol (app.extraction.base.Extractor).

El import de TesseractExtractor es local a la función a propósito: así
los tests que no usan EXTRACTOR=tesseract no necesitan cv2/pytesseract/fitz
instalados.
"""
from __future__ import annotations

from app.extraction.base import Extractor


def build_extractor(name: str) -> Extractor:
    if name == "tesseract":
        from app.extraction.tesseract.extractor import TesseractExtractor

        return TesseractExtractor()
    raise ValueError(f"Extractor desconocido: '{name}'")
