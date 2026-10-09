"""Contrato que debe cumplir cualquier extractor (Tesseract, LLM, etc.).

Cambiar de motor de extracción es escribir una clase que cumpla este
Protocol y elegirla en extraction/factory.py: la API, el servicio y el
frontend no cambian.
"""
from __future__ import annotations

from typing import Protocol

from app.domain.models import ExtractionResult


class Extractor(Protocol):
    name: str

    def extract(self, content: bytes, mime_type: str) -> ExtractionResult: ...
