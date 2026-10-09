"""Diccionario multiidioma de campos nutricionales y normalización de texto OCR."""
from __future__ import annotations

import unicodedata

FIELD_SYNONYMS: dict[str, list[str]] = {
    # "kcal" no vale como palabra clave suelta: es la unidad que va pegada al
    # propio número, así que una línea con dos valores "kcal" (100g + ración)
    # sin la palabra "energía" delante se automatcheaba contra sí misma y
    # cogía el valor de la ración en vez del de 100 g.
    "energy_kcal": ["valor energetico", "energia", "energy"],
    "fat_g": ["grasas", "materia grasa", "lipidos", "fat"],
    "carbohydrates_g": [
        "hidratos de carbono",
        "carbohidratos",
        "glucidos",
        "carbohydrate",
        "carbohydrates",
    ],
    "protein_g": ["proteinas", "proteina", "protein"],
}

# Líneas que mencionan un subcampo y no deben confundirse con el campo principal.
EXCLUDE_TERMS: dict[str, list[str]] = {
    "fat_g": ["saturad"],
    "carbohydrates_g": ["azucar"],
}

# Letras que Tesseract confunde con dígitos cuando aparecen junto a un número.
DIGIT_SUBSTITUTIONS: dict[str, str] = {
    "O": "0",
    "L": "1",
    "I": "1",
    "S": "5",
    "B": "8",
}


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def normalize_text(text: str) -> str:
    return strip_accents(text).lower()
