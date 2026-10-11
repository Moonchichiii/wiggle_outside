"""One typed Settings, read from the environment (.env.example lists every key).

Split only when a group earns its own file (PLAN section 6.1).
"""

import os
from dataclasses import dataclass
from typing import Final

from wiggle_outside.core.types import DeploymentMode

ENV_PREFIX: Final = "WO_"

# D32 as revised by TC-009 (Mats, 11 October 2026): the 20 s budget is split geocode 3 /
# places and weather 9 / model including its queue wait 6 / 2 s reserved for fallback
# assembly and rendering. The two Overpass attempts (the one permitted retry) share the
# 9 s: an attempt may use what is left of it, so the retry only happens when the first
# attempt failed early. Measured: a Vaxjo places query took 2 to 5 s when the public
# instance was healthy and 6 s or more under load; the model answered in 1.68 s. Every
# stage gets min(its budget, what is left), and the absolute 20 s deadline is
# authoritative when earlier stages use up their share. Figures: docs/evidence.
GEOCODE_BUDGET_S: Final = 3.0
PROVIDERS_BUDGET_S: Final = 9.0
MODEL_BUDGET_S: Final = 6.0
RENDER_RESERVE_S: Final = 2.0

# The hosted model key is read from the unprefixed name the Fly secret carries. It is
# never written to a file, a log or the repository (DEPLOYMENT section 3).
OPENROUTER_API_KEY_ENV: Final = "OPENROUTER_API_KEY"


def _env(name: str, default: str) -> str:
    return os.environ.get(f"{ENV_PREFIX}{name}", default)


def _env_int(name: str, default: int) -> int:
    return int(_env(name, str(default)))


def _env_bool(name: str, *, default: bool) -> bool:
    return _env(name, "true" if default else "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@dataclass(frozen=True, slots=True)
class Settings:
    mode: DeploymentMode
    host: str
    port: int
    db_path: str

    # Provider endpoints are configuration, never supplied by users (PLAN section 9).
    nominatim_url: str
    overpass_url: str
    open_meteo_url: str
    contact_email: str

    openrouter_url: str
    model_id: str
    openrouter_api_key: str | None

    ollama_url: str

    daily_run_limit: int
    deadline_seconds: int
    d39_enabled: bool

    @classmethod
    def from_env(cls) -> Settings:
        key = os.environ.get(OPENROUTER_API_KEY_ENV, "").strip()
        return cls(
            mode=DeploymentMode(_env("MODE", DeploymentMode.LOCAL.value)),
            host=_env("HOST", "127.0.0.1"),
            port=_env_int("PORT", 8000),
            db_path=_env("DB_PATH", "./data/wiggle.sqlite"),
            nominatim_url=_env("NOMINATIM_URL", "https://nominatim.openstreetmap.org"),
            overpass_url=_env("OVERPASS_URL", "https://overpass-api.de/api/interpreter"),
            open_meteo_url=_env("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast"),
            contact_email=_env("CONTACT_EMAIL", ""),
            openrouter_url=_env("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions"),
            model_id=_env("MODEL_ID", "google/gemma-4-26b-a4b-it"),
            openrouter_api_key=key or None,
            ollama_url=_env("OLLAMA_URL", "http://127.0.0.1:11434/api/chat"),
            daily_run_limit=_env_int("DAILY_RUN_LIMIT", 200),
            deadline_seconds=_env_int("DEADLINE_SECONDS", 20),
            d39_enabled=_env_bool("D39_ENABLED", default=True),
        )
