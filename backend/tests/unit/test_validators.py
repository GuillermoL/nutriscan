"""Tests de validadores: rangos plausibles, coherencia kJ/kcal y Atwater."""
from __future__ import annotations

import pytest

from app.domain.validators import (
    atwater_consistent,
    is_in_range,
    kj_kcal_consistent,
    macro_sum_valid,
)


@pytest.mark.parametrize(
    "field, value, expected",
    [
        ("energy_kcal", 0.0, True),
        ("energy_kcal", 900.0, True),
        ("energy_kcal", 900.1, False),
        ("energy_kcal", -1.0, False),
        ("fat_g", 100.0, True),
        ("fat_g", 100.1, False),
        ("protein_g", 50.0, True),
    ],
)
def test_is_in_range(field, value, expected):
    assert is_in_range(field, value) is expected


def test_kj_kcal_consistent_dentro_de_tolerancia():
    # 452 kcal * 4,184 = 1891,168 kJ
    assert kj_kcal_consistent(kj=1891, kcal=452) is True


def test_kj_kcal_inconsistente_fuera_de_tolerancia():
    assert kj_kcal_consistent(kj=1000, kcal=452) is False


def test_kj_kcal_ambos_cero_es_consistente():
    assert kj_kcal_consistent(kj=0, kcal=0) is True


def test_atwater_cuadra_dentro_de_tolerancia():
    # 9*21 + 4*58 + 4*6.5 = 447 kcal; declarado 452 kcal (~1.1% de diferencia)
    assert atwater_consistent(kcal=452, fat_g=21, carbohydrates_g=58, protein_g=6.5) is True


def test_atwater_no_cuadra_fuera_de_tolerancia():
    assert atwater_consistent(kcal=800, fat_g=21, carbohydrates_g=58, protein_g=6.5) is False


def test_macro_sum_valid_dentro_del_limite():
    assert macro_sum_valid(fat_g=21, carbohydrates_g=58, protein_g=6.5) is True


def test_macro_sum_valid_supera_el_limite():
    assert macro_sum_valid(fat_g=50, carbohydrates_g=40, protein_g=20) is False
