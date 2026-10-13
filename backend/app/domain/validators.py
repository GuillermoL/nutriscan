"""Validaciones físicas y de rango sobre valores ya extraídos.

Funciones puras: reciben números, no objetos del parser ni del OCR, para
poder testearlas sin imágenes ni Tesseract. Viven en el dominio (no en
extraction/tesseract/) porque son reglas de negocio compartidas por
cualquier extractor, no solo por el basado en OCR.
"""
from __future__ import annotations

RANGES: dict[str, tuple[float, float]] = {
    "energy_kcal": (0.0, 900.0),
    "fat_g": (0.0, 100.0),
    "carbohydrates_g": (0.0, 100.0),
    "protein_g": (0.0, 100.0),
}

KJ_TO_KCAL = 4.184
KJ_KCAL_TOLERANCE = 0.05
ATWATER_TOLERANCE = 0.15
MAX_MACRO_SUM_G = 100.0


def is_in_range(field: str, value: float) -> bool:
    low, high = RANGES[field]
    return low <= value <= high


def kj_kcal_consistent(kj: float, kcal: float, tolerance: float = KJ_KCAL_TOLERANCE) -> bool:
    expected_kj = kcal * KJ_TO_KCAL
    if expected_kj == 0:
        return kj == 0
    return abs(kj - expected_kj) / expected_kj <= tolerance


def atwater_consistent(
    kcal: float,
    fat_g: float,
    carbohydrates_g: float,
    protein_g: float,
    tolerance: float = ATWATER_TOLERANCE,
) -> bool:
    expected_kcal = 9 * fat_g + 4 * carbohydrates_g + 4 * protein_g
    if expected_kcal == 0:
        return kcal == 0
    return abs(kcal - expected_kcal) / expected_kcal <= tolerance


def macro_sum_valid(
    fat_g: float, carbohydrates_g: float, protein_g: float, max_total: float = MAX_MACRO_SUM_G
) -> bool:
    return (fat_g + carbohydrates_g + protein_g) <= max_total
