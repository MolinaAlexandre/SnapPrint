"""Chargement centralisé de la configuration depuis .env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Charge le .env situé dans backend/
load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # Muse (Meta)
    MUSE_API_KEY: str = os.getenv("MUSE_API_KEY", "")
    MUSE_API_BASE: str = os.getenv("MUSE_API_BASE", "https://api.meta.ai/v1")
    MUSE_SPARK_MODEL: str = os.getenv("MUSE_SPARK_MODEL", "muse-spark-1.3")
    MUSE_VOICE_MODEL: str = os.getenv("MUSE_VOICE_MODEL", "muse-voice-transcribe-1.0")

    # Baseten (fallback)
    BASETEN_API_KEY: str = os.getenv("BASETEN_API_KEY", "")
    BASETEN_MODEL: str = os.getenv("BASETEN_MODEL", "meta-models/muse-spark-open-1026")
    BASETEN_API_BASE: str = os.getenv("BASETEN_API_BASE", "https://inference.baseten.co/v1")

    # SAM — par défaut sur la même Model API que Muse (même clé/endpoint).
    SAM_API_KEY: str = os.getenv("SAM_API_KEY", "") or os.getenv("MUSE_API_KEY", "")
    SAM_API_BASE: str = os.getenv("SAM_API_BASE", "") or os.getenv(
        "MUSE_API_BASE", "https://api.meta.ai/v1"
    )
    SAM_MODEL: str = os.getenv("SAM_MODEL", "sam-3.1")
    # Phrases nominales envoyées à SAM pour détecter l'objet et la pièce.
    SAM_OBJECT_PROMPT: str = os.getenv("SAM_OBJECT_PROMPT", "the main object")
    SAM_COIN_PROMPT: str = os.getenv("SAM_COIN_PROMPT", "coin")

    # Pipeline
    USE_MOCK_VISION: bool = _as_bool(os.getenv("USE_MOCK_VISION"), default=True)
    OPENSCAD_BIN: str = os.getenv("OPENSCAD_BIN", "openscad")
    OUTPUT_DIR: Path = BASE_DIR / os.getenv("OUTPUT_DIR", "outputs")

    # Chemin vers la bibliothèque SCAD (utilisée comme include dir pour OpenSCAD)
    CAD_LIB_DIR: Path = BASE_DIR / "cad"

    def __init__(self) -> None:
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
