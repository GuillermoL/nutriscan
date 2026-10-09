"""Tests del parser contra fixtures de texto OCR 'sucio'.

Cada fixture en tests/fixtures/ simula la salida de Tesseract para un
formato distinto de etiqueta. El parser debe funcionar por línea y
proximidad de palabra clave, no asumir tablas perfectas.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.extraction.tesseract.parser import parse_label_text

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_tabla_vertical_clara_camino_feliz():
    result = parse_label_text(load_fixture("tabla_vertical_clara.txt"))

    assert result["energy_kcal"].value == pytest.approx(452.0)
    assert result["energy_kcal"].raw_text == "Valor energetico 1891 kJ / 452 kcal"
    assert result["fat_g"].value == pytest.approx(21.0)
    assert result["carbohydrates_g"].value == pytest.approx(58.0)
    assert result["protein_g"].value == pytest.approx(6.5)
    for field in result.values():
        assert field.reason is None


def test_tabla_horizontal_linea_unica():
    result = parse_label_text(load_fixture("horizontal_linea_unica.txt"))

    assert result["energy_kcal"].value == pytest.approx(405.0)
    assert result["fat_g"].value == pytest.approx(20.0)
    assert result["carbohydrates_g"].value == pytest.approx(60.0)
    assert result["protein_g"].value == pytest.approx(8.0)


def test_etiqueta_bilingue():
    result = parse_label_text(load_fixture("bilingue.txt"))

    assert result["energy_kcal"].value == pytest.approx(358.0)
    assert result["fat_g"].value == pytest.approx(15.0)
    assert result["carbohydrates_g"].value == pytest.approx(50.0)
    assert result["protein_g"].value == pytest.approx(7.0)


def test_texto_corrido_sin_tabla():
    result = parse_label_text(load_fixture("texto_corrido.txt"))

    assert result["energy_kcal"].value == pytest.approx(390.0)
    assert result["fat_g"].value == pytest.approx(18.0)
    assert result["carbohydrates_g"].value == pytest.approx(45.0)
    assert result["protein_g"].value == pytest.approx(9.0)


def test_coma_decimal():
    result = parse_label_text(load_fixture("coma_decimal.txt"))

    assert result["energy_kcal"].value == pytest.approx(298.5)
    assert result["fat_g"].value == pytest.approx(12.3)
    assert result["carbohydrates_g"].value == pytest.approx(35.0)
    assert result["protein_g"].value == pytest.approx(4.8)


def test_valor_menor_que():
    result = parse_label_text(load_fixture("valor_menor_que.txt"))

    fat = result["fat_g"]
    assert fat.value == pytest.approx(0.5)
    assert fat.reason is not None
    assert "<" in fat.reason


def test_coma_decimal_perdida_por_el_ocr_no_se_lee_como_entero():
    """"05g" (el OCR se comió la coma de "0,5g") debe leerse como 0.5, no como 5."""
    result = parse_label_text(load_fixture("coma_perdida.txt"))

    carbs = result["carbohydrates_g"]
    assert carbs.value == pytest.approx(0.5)
    assert carbs.reason is not None and "coma decimal perdida" in carbs.reason

    protein = result["protein_g"]
    assert protein.value == pytest.approx(0.5)


def test_columna_100g_elegida_frente_a_racion():
    result = parse_label_text(load_fixture("columna_100g_y_racion.txt"))

    assert result["energy_kcal"].value == pytest.approx(405.0)
    assert result["fat_g"].value == pytest.approx(20.0)
    assert result["carbohydrates_g"].value == pytest.approx(60.0)
    assert result["protein_g"].value == pytest.approx(8.0)


def test_solo_kj_se_convierte_a_kcal():
    energy = parse_label_text(load_fixture("solo_kj.txt"))["energy_kcal"]

    assert energy.value == pytest.approx(406.3, abs=0.05)
    assert energy.source == "ocr_kj_converted"
    assert energy.reason is not None
    assert "kJ" in energy.reason


def test_subcampos_saturadas_y_azucares_no_se_confunden():
    result = parse_label_text(load_fixture("subcampos_excluidos.txt"))

    assert result["fat_g"].value == pytest.approx(25.0)
    assert result["carbohydrates_g"].value == pytest.approx(55.0)
    assert result["protein_g"].value == pytest.approx(5.0)
    assert result["energy_kcal"].value == pytest.approx(450.0)


def test_coincidencia_difusa_tolera_error_ocr_en_palabra_clave():
    protein = parse_label_text(load_fixture("fuzzy_proteinas.txt"))["protein_g"]

    assert protein.value == pytest.approx(6.0)


def test_sin_coincidencias_todos_los_campos_not_found():
    result = parse_label_text(load_fixture("sin_coincidencias.txt"))

    for field_name, field in result.items():
        assert field.value is None, f"{field_name} deberia ser not_found"
        assert field.raw_text is None
        assert field.reason == "No se encontró la palabra clave"


def test_confusion_de_caracteres_ocr_en_numeros():
    result = parse_label_text(load_fixture("confusion_ocr_digitos.txt"))

    energy = result["energy_kcal"]
    assert energy.value == pytest.approx(406.0)
    assert energy.reason is not None and "O→0" in energy.reason

    fat = result["fat_g"]
    assert fat.value == pytest.approx(21.0)
    assert fat.reason is not None and "I→1" in fat.reason

    carbs = result["carbohydrates_g"]
    assert carbs.value == pytest.approx(58.0)
    assert carbs.reason is not None and "B→8" in carbs.reason

    protein = result["protein_g"]
    assert protein.value == pytest.approx(5.2)
    assert protein.reason is not None and "S→5" in protein.reason
