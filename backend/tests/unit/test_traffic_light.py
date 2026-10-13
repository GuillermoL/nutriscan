"""Límites exactos del semáforo, sentido invertido en proteínas, validación
de configuración y la regla de que not_found nunca tiene color."""
from __future__ import annotations

import pytest

from app.domain.models import ExtractionResult, FieldStatus, NutritionField, TrafficLightColor
from app.domain.traffic_light import (
    InvalidTrafficLightConfigError,
    TrafficLightRule,
    build_rules,
    classify_value,
    overall_color,
)
from app.services.label_analysis import analyze_label

FAT_RULE = TrafficLightRule(direction="lower_is_better", green_max=3.0, red_min=17.5)
PROTEIN_RULE = TrafficLightRule(direction="higher_is_better", green_min=10.0, red_max=3.0)


@pytest.mark.parametrize(
    "value, expected",
    [
        (3.0, TrafficLightColor.GREEN),
        (17.5, TrafficLightColor.AMBER),
        (17.6, TrafficLightColor.RED),
    ],
)
def test_fat_thresholds_are_exact(value: float, expected: TrafficLightColor) -> None:
    assert classify_value(value, FAT_RULE) is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (10.0, TrafficLightColor.GREEN),
        (9.99, TrafficLightColor.AMBER),
        (3.0, TrafficLightColor.AMBER),
        (2.99, TrafficLightColor.RED),
    ],
)
def test_protein_sense_is_inverted(value: float, expected: TrafficLightColor) -> None:
    assert classify_value(value, PROTEIN_RULE) is expected


def test_lower_is_better_requires_green_max_below_red_min() -> None:
    with pytest.raises(InvalidTrafficLightConfigError):
        TrafficLightRule(direction="lower_is_better", green_max=20.0, red_min=10.0)


def test_higher_is_better_requires_red_max_below_green_min() -> None:
    with pytest.raises(InvalidTrafficLightConfigError):
        TrafficLightRule(direction="higher_is_better", green_min=5.0, red_max=8.0)


def test_unknown_direction_is_rejected() -> None:
    with pytest.raises(InvalidTrafficLightConfigError):
        TrafficLightRule(direction="sideways")  # type: ignore[arg-type]


def test_build_rules_from_raw_yaml_dict() -> None:
    raw = {
        "fat_g": {"direction": "lower_is_better", "green_max": 3.0, "red_min": 17.5},
        "protein_g": {"direction": "higher_is_better", "green_min": 10.0, "red_max": 3.0},
    }
    rules = build_rules(raw)
    assert rules["fat_g"] == FAT_RULE
    assert rules["protein_g"] == PROTEIN_RULE


class _StubExtractor:
    name = "stub@1.0"

    def __init__(self, result: ExtractionResult) -> None:
        self._result = result

    def extract(self, content: bytes, mime_type: str) -> ExtractionResult:
        return self._result


def test_not_found_field_never_gets_a_color() -> None:
    fields = {
        "energy_kcal": NutritionField(value=None, unit="kcal", status=FieldStatus.NOT_FOUND, confidence=0.0),
        "fat_g": NutritionField(value=0.0, unit="g", status=FieldStatus.OK, confidence=0.9, raw_text="Grasas 0 g"),
        "carbohydrates_g": NutritionField(value=0.0, unit="g", status=FieldStatus.OK, confidence=0.9),
        "protein_g": NutritionField(value=0.0, unit="g", status=FieldStatus.NOT_FOUND, confidence=0.0),
    }
    extraction = ExtractionResult(basis="per_100g", fields=fields, checks=[], warnings=[], extractor="stub@1.0")
    rules = {
        "energy_kcal": TrafficLightRule(direction="lower_is_better", green_max=150, red_min=400),
        "fat_g": FAT_RULE,
        "carbohydrates_g": TrafficLightRule(direction="lower_is_better", green_max=15.0, red_min=45.0),
        "protein_g": PROTEIN_RULE,
    }

    result = analyze_label(
        content=b"irrelevant", mime_type="image/jpeg", extractor=_StubExtractor(extraction), traffic_light_rules=rules
    )

    assert result.traffic_light["energy_kcal"] is None
    assert result.traffic_light["protein_g"] is None
    assert result.traffic_light["fat_g"] is TrafficLightColor.GREEN


@pytest.mark.parametrize(
    "colors, expected",
    [
        ({"a": TrafficLightColor.GREEN, "b": TrafficLightColor.GREEN}, TrafficLightColor.GREEN),
        ({"a": TrafficLightColor.GREEN, "b": TrafficLightColor.AMBER}, TrafficLightColor.AMBER),
        ({"a": TrafficLightColor.GREEN, "b": TrafficLightColor.RED}, TrafficLightColor.RED),
        ({"a": TrafficLightColor.AMBER, "b": TrafficLightColor.RED}, TrafficLightColor.RED),
        ({"a": None, "b": TrafficLightColor.GREEN}, TrafficLightColor.GREEN),
        ({"a": None, "b": None}, None),
    ],
)
def test_overall_color_is_the_worst_of_the_known_colors(colors, expected) -> None:
    assert overall_color(colors) is expected
