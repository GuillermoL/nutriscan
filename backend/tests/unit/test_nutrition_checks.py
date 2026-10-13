"""Tests de los checks de consistencia compartidos (kJ/kcal, Atwater, suma de macros)."""
from __future__ import annotations

from app.domain.models import FieldStatus, NutritionField
from app.domain.nutrition_checks import apply_check_results, extract_kj_from_raw, run_checks


def _field(value: float | None, raw_text: str | None = None) -> NutritionField:
    return NutritionField(
        value=value,
        unit="g",
        status=FieldStatus.OK if value is not None else FieldStatus.NOT_FOUND,
        confidence=0.9 if value is not None else 0.0,
        raw_text=raw_text,
    )


def test_extract_kj_from_raw_reads_grouped_european_number() -> None:
    assert extract_kj_from_raw("Valor energético 1.891 kJ / 452 kcal") == 1891


def test_extract_kj_from_raw_without_kj_returns_none() -> None:
    assert extract_kj_from_raw("452 kcal") is None


def test_run_checks_flags_kj_kcal_mismatch() -> None:
    fields = {
        "energy_kcal": _field(452, raw_text="1000 kJ / 452 kcal"),
        "fat_g": _field(21),
        "carbohydrates_g": _field(58),
        "protein_g": _field(6.5),
    }
    checks = run_checks(fields)
    kj_check = next(check for check in checks if check.name == "kj_kcal_consistency")
    assert kj_check.passed is False


def test_apply_check_results_downgrades_energy_on_kj_mismatch() -> None:
    fields = {
        "energy_kcal": _field(452, raw_text="1000 kJ / 452 kcal"),
        "fat_g": _field(21),
        "carbohydrates_g": _field(58),
        "protein_g": _field(6.5),
    }
    checks = run_checks(fields)
    updated = apply_check_results(fields, checks)
    assert updated["energy_kcal"].status == FieldStatus.DOUBTFUL


def test_apply_check_results_never_upgrades_a_not_found_field() -> None:
    fields = {
        "energy_kcal": _field(None),
        "fat_g": _field(21),
        "carbohydrates_g": _field(58),
        "protein_g": _field(6.5),
    }
    checks = run_checks(fields)
    updated = apply_check_results(fields, checks)
    assert updated["energy_kcal"].status == FieldStatus.NOT_FOUND
