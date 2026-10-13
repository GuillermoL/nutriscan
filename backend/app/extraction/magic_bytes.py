"""Detección del tipo real de archivo por magic bytes, nunca por extensión.

Compartida por todos los extractores (Tesseract, Claude): cada uno decide
qué hacer con el documento, pero ninguno se fía del Content-Type declarado.
"""
from __future__ import annotations

from app.domain.errors import UnsupportedFormatError


def detect_mime_type(content: bytes) -> str:
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
