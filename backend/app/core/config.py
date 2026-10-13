"""Configuración de la aplicación y carga de los umbrales del semáforo.

La lectura del YAML es I/O y vive aquí a propósito: app.domain.traffic_light
solo valida y clasifica, nunca toca el disco.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.traffic_light import InvalidTrafficLightConfigError, TrafficLightRule, build_rules

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_TRAFFIC_LIGHT_PATH = BASE_DIR / "config" / "traffic_light.yaml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    extractor: str = "hybrid"
    max_upload_mb: int = 10
    ocr_languages: str = "spa+eng"
    traffic_light_config_path: Path = DEFAULT_TRAFFIC_LIGHT_PATH
    cors_origins: list[str] = ["http://localhost:4200"]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_traffic_light_rules(path: Path) -> dict[str, TrafficLightRule]:
    """Lee y valida el YAML de umbrales. Si es inválido, lanza al arrancar."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InvalidTrafficLightConfigError(f"No se encuentra {path}") from exc
    except yaml.YAMLError as exc:
        raise InvalidTrafficLightConfigError(f"YAML inválido en {path}: {exc}") from exc

    rules = raw.get("rules") if isinstance(raw, dict) else None
    if not rules:
        raise InvalidTrafficLightConfigError(f"{path} no define la clave 'rules'")

    return build_rules(rules)


@lru_cache
def get_traffic_light_rules() -> dict[str, TrafficLightRule]:
    settings = get_settings()
    return load_traffic_light_rules(settings.traffic_light_config_path)
