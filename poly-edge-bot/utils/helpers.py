"""
utils/helpers.py — Utility functions
Funciones auxiliares del bot
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Config loader / Cargador de configuración
# ---------------------------------------------------------------------------

def load_config(config_path: str = "config/config.yaml") -> dict[str, Any]:
    """Load YAML config and overlay .env variables.
    Carga config YAML y superpone variables de .env."""

    load_dotenv()

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # .env overrides / Sobrecargas de .env
    if os.getenv("DAILY_LOSS_LIMIT_USD"):
        cfg["risk"]["daily_loss_limit_usd"] = float(os.getenv("DAILY_LOSS_LIMIT_USD"))
    if os.getenv("MAX_POSITION_USD"):
        cfg["risk"]["max_position_usd"] = float(os.getenv("MAX_POSITION_USD"))

    return cfg


# ---------------------------------------------------------------------------
# Pydantic models for typed market data / Modelos tipados
# ---------------------------------------------------------------------------

class MarketToken(BaseModel):
    """A single outcome token in a market."""
    token_id: str
    outcome: str
    price: float = 0.0


class MarketInfo(BaseModel):
    """Enriched market information combining Gamma + CLOB data.
    Información enriquecida de mercado combinando Gamma + CLOB."""

    condition_id: str = ""
    question: str = ""
    slug: str = ""
    category: str = ""
    end_date: str = ""
    active: bool = True
    closed: bool = False
    liquidity: float = 0.0
    volume: float = 0.0
    volume_24h: float = 0.0
    tokens: list[MarketToken] = Field(default_factory=list)
    best_bid: float = 0.0
    best_ask: float = 0.0
    midpoint: float = 0.0
    spread: float = 0.0


class Opportunity(BaseModel):
    """A detected trading opportunity / Oportunidad de trading detectada."""

    market: MarketInfo
    side: str  # BUY or SELL
    token_id: str
    outcome: str
    market_price: float
    model_prob: float
    edge: float
    kelly_fraction: float
    suggested_size_usd: float
    reason: str = ""


# ---------------------------------------------------------------------------
# Misc helpers / Helpers varios
# ---------------------------------------------------------------------------

def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert to float / Conversión segura a float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def hours_until(iso_date: str) -> float:
    """Hours from now until an ISO-8601 date string.
    Horas desde ahora hasta una fecha ISO-8601."""
    from datetime import datetime, timezone

    try:
        target = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = target - now
        return max(delta.total_seconds() / 3600, 0)
    except Exception:
        return float("inf")
