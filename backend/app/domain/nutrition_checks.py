"""Checks de consistencia física sobre un conjunto de NutritionField ya extraído.

Puro dominio: opera sobre NutritionField/CheckResult, sin saber nada del
extractor que produjo los valores (OCR, IA o el que sea), así que lo
reutiliza cualquier Extractor para que el criterio de "dudoso" sea el
mismo sin importar el origen de los datos.
"""
from __future__ import annotations

import re
from dataclasses import replace

from app.domain.models import CheckResult, FieldStatus, NutritionField
from app.domain.validators import atwater_consistent, kj_kcal_consistent, macro_sum_valid

_KJ_PATTERN = re.compile(r"([\d.,]{1,8})\s*kj")
_THOUSANDS_GROUPED = re.compile(r"\d{1,3}(\.\d{3})+$")


def _parse_european_number(raw: str) -> float:
    """Convierte "1.437" o "1.437,5" (miles con '.', decimales con ',') a float.

    Sin coma, un único "." seguido de grupos de 3 dígitos es separador de
    miles (p. ej. "1.437"); en cualquier otro caso (p. ej. "4.18") es un
    separador decimal normal.
    """
    if "," in raw:
        integer_part, _, decimal_part = raw.rpartition(",")
        return float(f"{integer_part.replace('.', '')}.{decimal_part}")
    if _THOUSANDS_GROUPED.fullmatch(raw):
        return float(raw.replace(".", ""))
    return float(raw)


def extract_kj_from_raw(raw_text: str | None) -> float | None:
    if not raw_text:
        return None
    match = _KJ_PATTERN.search(raw_text.lower())
    if not match:
        return None
    return _parse_european_number(match.group(1))


def downgrade(nutrition_field: NutritionField, reason: str) -> NutritionField:
    if nutrition_field.status == FieldStatus.NOT_FOUND:
        return nutrition_field
    combined_reason = f"{nutrition_field.reason}; {reason}" if nutrition_field.reason else reason
    return replace(
        nutrition_field,
        status=FieldStatus.DOUBTFUL,
        confidence=round(nutrition_field.confidence * 0.7, 2),
        reason=combined_reason,
    )


def run_checks(fields: dict[str, NutritionField]) -> list[CheckResult]:
    checks: list[CheckResult] = []
    energy, fat, carbs, protein = (
        fields["energy_kcal"],
        fields["fat_g"],
        fields["carbohydrates_g"],
        fields["protein_g"],
    )

    kj_value = extract_kj_from_raw(energy.raw_text) if energy.value is not None else None
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


def apply_check_results(
    fields: dict[str, NutritionField], checks: list[CheckResult]
) -> dict[str, NutritionField]:
    updated = dict(fields)
    by_name = {check.name: check for check in checks}

    kj_check = by_name.get("kj_kcal_consistency")
    if kj_check and not kj_check.passed:
        updated["energy_kcal"] = downgrade(updated["energy_kcal"], "Incoherencia kJ/kcal")

    atwater_check = by_name.get("atwater_energy")
    if atwater_check and not atwater_check.passed and not atwater_check.detail.startswith("No evaluable"):
        for name in ("energy_kcal", "fat_g", "carbohydrates_g", "protein_g"):
            updated[name] = downgrade(updated[name], "Incoherencia con el cálculo de Atwater")

    macro_check = by_name.get("macro_sum")
    if macro_check and not macro_check.passed:
        for name in ("fat_g", "carbohydrates_g", "protein_g"):
            updated[name] = downgrade(updated[name], "Suma de macronutrientes superior a 100 g")

    return updated
