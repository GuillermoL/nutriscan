"""Carga del YAML real de umbrales y detección de configuración inválida."""
from __future__ import annotations

import pytest

from app.core.config import DEFAULT_TRAFFIC_LIGHT_PATH, load_traffic_light_rules
from app.domain.traffic_light import InvalidTrafficLightConfigError


def test_default_config_loads_and_matches_documented_thresholds() -> None:
    rules = load_traffic_light_rules(DEFAULT_TRAFFIC_LIGHT_PATH)

    assert rules["fat_g"].green_max == 3.0
    assert rules["fat_g"].red_min == 17.5
    assert rules["protein_g"].green_min == 10.0
    assert rules["protein_g"].red_max == 3.0


def test_missing_file_raises_invalid_config_error(tmp_path) -> None:
    with pytest.raises(InvalidTrafficLightConfigError):
        load_traffic_light_rules(tmp_path / "no_existe.yaml")


def test_invalid_yaml_rules_raise_invalid_config_error(tmp_path) -> None:
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text(
        "basis: per_100g\nrules:\n  fat_g: {green_max: 20.0, red_min: 10.0, direction: lower_is_better}\n",
        encoding="utf-8",
    )
    with pytest.raises(InvalidTrafficLightConfigError):
        load_traffic_light_rules(bad_config)


def test_missing_rules_key_raises_invalid_config_error(tmp_path) -> None:
    empty_config = tmp_path / "empty.yaml"
    empty_config.write_text("basis: per_100g\n", encoding="utf-8")
    with pytest.raises(InvalidTrafficLightConfigError):
        load_traffic_light_rules(empty_config)
