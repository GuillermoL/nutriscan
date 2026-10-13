"""Semáforo nutricional: regla de dominio pura, sin I/O.

Los umbrales se cargan una vez al arrancar desde config/traffic_light.yaml
(ver app.core.config) y se pasan aquí ya validados. Esta clasificación no
sabe nada de OCR, de HTTP ni de FastAPI: solo recibe un número y una regla.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.domain.models import TrafficLightColor

Direction = Literal["lower_is_better", "higher_is_better"]


class InvalidTrafficLightConfigError(ValueError):
    """El YAML de umbrales no es coherente (p. ej. green_max >= red_min)."""


@dataclass(frozen=True)
class TrafficLightRule:
    direction: Direction
    green_max: float | None = None
    red_min: float | None = None
    green_min: float | None = None
    red_max: float | None = None

    def __post_init__(self) -> None:
        if self.direction == "lower_is_better":
            if self.green_max is None or self.red_min is None:
                raise InvalidTrafficLightConfigError(
                    "lower_is_better requiere green_max y red_min"
                )
            if not self.green_max < self.red_min:
                raise InvalidTrafficLightConfigError(
                    f"green_max ({self.green_max}) debe ser menor que red_min ({self.red_min})"
                )
        elif self.direction == "higher_is_better":
            if self.green_min is None or self.red_max is None:
                raise InvalidTrafficLightConfigError(
                    "higher_is_better requiere green_min y red_max"
                )
            if not self.red_max < self.green_min:
                raise InvalidTrafficLightConfigError(
                    f"red_max ({self.red_max}) debe ser menor que green_min ({self.green_min})"
                )
        else:
            raise InvalidTrafficLightConfigError(f"direction desconocida: {self.direction}")


def classify_value(value: float, rule: TrafficLightRule) -> TrafficLightColor:
    if rule.direction == "lower_is_better":
        if value <= rule.green_max:
            return TrafficLightColor.GREEN
        if value > rule.red_min:
            return TrafficLightColor.RED
        return TrafficLightColor.AMBER

    if value >= rule.green_min:
        return TrafficLightColor.GREEN
    if value < rule.red_max:
        return TrafficLightColor.RED
    return TrafficLightColor.AMBER


def build_rules(raw_rules: dict[str, dict]) -> dict[str, TrafficLightRule]:
    return {field_name: TrafficLightRule(**rule) for field_name, rule in raw_rules.items()}


def overall_color(colors: dict[str, TrafficLightColor | None]) -> TrafficLightColor | None:
    """Semáforo único del producto: el peor color de entre los campos
    encontrados ("worst wins"). Un solo nutriente en rojo basta para que el
    producto en conjunto se pinte en rojo. Los campos sin color (not_found)
    no cuentan ni a favor ni en contra; si no hay ningún campo con color,
    el resultado es None (no se puede juzgar el producto).
    """
    known = [color for color in colors.values() if color is not None]
    if not known:
        return None
    if TrafficLightColor.RED in known:
        return TrafficLightColor.RED
    if TrafficLightColor.AMBER in known:
        return TrafficLightColor.AMBER
    return TrafficLightColor.GREEN
