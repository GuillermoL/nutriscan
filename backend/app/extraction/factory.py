"""Elige el extractor de etiquetas según la variable de entorno EXTRACTOR.

Sustituir Tesseract por otro motor (p. ej. un extractor basado en LLM) es
añadir una rama aquí: la API, el servicio y el frontend no cambian porque
todos cumplen el mismo Protocol (app.extraction.base.Extractor).

Los imports de cada extractor concreto son locales a la función a
propósito: así los tests que no usan EXTRACTOR=tesseract no necesitan
cv2/pytesseract/fitz instalados, y los que no usan EXTRACTOR=claude no
necesitan el SDK de Anthropic.
"""
from __future__ import annotations

from app.extraction.base import Extractor


def build_extractor(name: str) -> Extractor:
    if name == "tesseract":
        from app.extraction.tesseract.extractor import TesseractExtractor

        return TesseractExtractor()
    if name == "claude":
        from app.extraction.claude.extractor import ClaudeExtractor

        return ClaudeExtractor()
    if name == "hybrid":
        from app.extraction.claude.extractor import ClaudeExtractor
        from app.extraction.hybrid import HybridExtractor
        from app.extraction.tesseract.extractor import TesseractExtractor

        return HybridExtractor(primary=TesseractExtractor(), fallback=ClaudeExtractor())
    raise ValueError(f"Extractor desconocido: '{name}'")
