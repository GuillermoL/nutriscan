"""Extrae los cuatro campos nutricionales de un texto OCR.

Trabaja por línea y por proximidad de palabra clave, no asume tablas
perfectas: para cada línea candidata busca la palabra clave del campo
(coincidencia exacta o difusa) y luego el primer número con la unidad
correcta a continuación de esa palabra.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from app.extraction.tesseract.synonyms import (
    DIGIT_SUBSTITUTIONS,
    EXCLUDE_TERMS,
    FIELD_SYNONYMS,
    normalize_text,
)

KJ_TO_KCAL = 4.184
FUZZY_THRESHOLD = 85
NOT_FOUND_REASON = "No se encontró la palabra clave"

# Dígitos 0-9 más las letras que Tesseract confunde con ellos, en ambos casos.
_NUMBER_CHARS = "0-9OoLlIiSsBb"
_NUMBER_TOKEN = rf"(<\s*)?([{_NUMBER_CHARS}]{{1,4}}(?:[.,][{_NUMBER_CHARS}]{{1,2}})?)"


@dataclass
class ParsedField:
    value: float | None
    unit: str
    raw_text: str | None
    source: str | None
    reason: str | None = None


def _correct_number_token(token: str) -> tuple[float, list[str]]:
    corrections: list[str] = []
    chars: list[str] = []
    for ch in token:
        if ch.isdigit():
            chars.append(ch)
        elif ch in ".,":
            chars.append(".")
        else:
            substitute = DIGIT_SUBSTITUTIONS.get(ch.upper())
            if substitute is None:
                chars.append(ch)
            else:
                chars.append(substitute)
                corrections.append(f"{ch.upper()}→{substitute}")

    digits = "".join(chars)
    if "." not in digits and len(digits) > 1 and digits[0] == "0":
        # El OCR a veces se come la coma decimal: "0,5" queda en "05". Nadie
        # imprime gramos con un cero a la izquierda como entero, así que
        # tratamos ese patrón como coma perdida en vez de como "5".
        digits = f"{digits[0]}.{digits[1:]}"
        corrections.append("coma decimal perdida tras el 0 inicial")

    return float(digits), corrections


def _fuzzy_keyword_end(normalized_line: str, synonyms: list[str]) -> int | None:
    words = list(re.finditer(r"\S+", normalized_line))
    best_end: int | None = None
    best_score = 0.0
    for synonym in synonyms:
        window_size = len(synonym.split())
        for i in range(len(words) - window_size + 1):
            window = words[i : i + window_size]
            window_text = " ".join(match.group() for match in window)
            score = fuzz.ratio(window_text, synonym)
            if score >= FUZZY_THRESHOLD and score > best_score:
                best_score = score
                best_end = window[-1].end()
    return best_end


def _keyword_end_position(normalized_line: str, synonyms: list[str]) -> int | None:
    for synonym in synonyms:
        index = normalized_line.find(synonym)
        if index != -1:
            return index + len(synonym)
    return _fuzzy_keyword_end(normalized_line, synonyms)


def _find_matches_after(tail: str, unit: str) -> list[re.Match]:
    pattern = re.compile(_NUMBER_TOKEN + r"\s*" + unit + r"\b")
    return list(pattern.finditer(tail))


def _build_result(match: re.Match) -> dict:
    approx_marker, raw_token = match.group(1), match.group(2)
    value, corrections = _correct_number_token(raw_token)
    reasons = []
    if approx_marker:
        reasons.append(f'Valor declarado como límite ("<{raw_token}")')
    if corrections:
        reasons.append("Carácter ambiguo corregido (" + ", ".join(corrections) + ")")
    return {"value": value, "reason": "; ".join(reasons) if reasons else None}


def _detect_hundred_gram_column(normalized_lines: list[str]) -> int:
    hundred_markers = ("100 g", "100g", "100 ml", "100ml")
    serving_markers = ("racion", "porcion", "serving")
    for line in normalized_lines:
        hundred_positions = [line.find(marker) for marker in hundred_markers if marker in line]
        serving_positions = [line.find(marker) for marker in serving_markers if marker in line]
        if hundred_positions and serving_positions:
            return 0 if min(hundred_positions) < min(serving_positions) else 1
    return 0


def _not_found(unit: str) -> ParsedField:
    return ParsedField(value=None, unit=unit, raw_text=None, source=None, reason=NOT_FOUND_REASON)


def _parse_macro(
    field: str, lines: list[str], normalized_lines: list[str], column_index: int
) -> ParsedField:
    synonyms = FIELD_SYNONYMS[field]
    excludes = EXCLUDE_TERMS.get(field, [])
    for original, normalized in zip(lines, normalized_lines):
        if any(term in normalized for term in excludes):
            continue
        end = _keyword_end_position(normalized, synonyms)
        if end is None:
            continue
        matches = _find_matches_after(normalized[end:], unit="g")
        if not matches:
            continue
        match = matches[column_index] if column_index < len(matches) else matches[0]
        result = _build_result(match)
        return ParsedField(
            value=result["value"],
            unit="g",
            raw_text=original.strip(),
            source="ocr",
            reason=result["reason"],
        )
    return _not_found("g")


def _parse_energy(
    lines: list[str], normalized_lines: list[str], column_index: int
) -> ParsedField:
    synonyms = FIELD_SYNONYMS["energy_kcal"]
    for original, normalized in zip(lines, normalized_lines):
        end = _keyword_end_position(normalized, synonyms)
        if end is None:
            continue
        tail = normalized[end:]

        kcal_matches = _find_matches_after(tail, unit="kcal")
        if kcal_matches:
            match = kcal_matches[column_index] if column_index < len(kcal_matches) else kcal_matches[0]
            result = _build_result(match)
            return ParsedField(
                value=result["value"],
                unit="kcal",
                raw_text=original.strip(),
                source="ocr",
                reason=result["reason"],
            )

        kj_matches = _find_matches_after(tail, unit="kj")
        if kj_matches:
            match = kj_matches[column_index] if column_index < len(kj_matches) else kj_matches[0]
            result = _build_result(match)
            kcal_value = round(result["value"] / KJ_TO_KCAL, 1)
            conversion_note = f'Convertido desde kJ ({result["value"]:g} kJ ÷ 4,184)'
            reason = f'{result["reason"]}; {conversion_note}' if result["reason"] else conversion_note
            return ParsedField(
                value=kcal_value,
                unit="kcal",
                raw_text=original.strip(),
                source="ocr_kj_converted",
                reason=reason,
            )
    return _not_found("kcal")


def parse_label_text(text: str) -> dict[str, ParsedField]:
    lines = text.splitlines()
    normalized_lines = [normalize_text(line) for line in lines]
    column_index = _detect_hundred_gram_column(normalized_lines)

    return {
        "energy_kcal": _parse_energy(lines, normalized_lines, column_index),
        "fat_g": _parse_macro("fat_g", lines, normalized_lines, column_index),
        "carbohydrates_g": _parse_macro("carbohydrates_g", lines, normalized_lines, column_index),
        "protein_g": _parse_macro("protein_g", lines, normalized_lines, column_index),
    }
