"""
core/data_api.py — Polymarket Data API client
Cliente de la Data API de Polymarket para portfolio y estadísticas

The Data API provides user-level data: positions, PnL, trade history.
La Data API provee datos a nivel usuario: posiciones, PnL, historial.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from loguru import logger


class DataAPI:
    """Client for Polymarket's Data API / Cliente para la Data API."""

    BASE_URL = "https://data-api.polymarket.com"

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv("DATA_API_HOST", self.BASE_URL)

    def _get(self, endpoint: str, params: Optional[dict] = None) -> Any:
        """HTTP GET request / Petición GET HTTP."""
        url = f"{self.base_url}{endpoint}"
        try:
            resp = httpx.get(url, params=params, timeout=15.0)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Data API HTTP error: {e.response.status_code} — {url}")
            return None
        except Exception as e:
            logger.error(f"Data API request failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Market-level data / Datos a nivel de mercado
    # ------------------------------------------------------------------

    def get_market_trades(self, condition_id: str, limit: int = 50) -> list[dict]:
        """Get recent trades for a market / Obtener trades recientes de un mercado."""
        data = self._get("/trades", {"market": condition_id, "limit": limit})
        return data if isinstance(data, list) else []

    def get_market_prices_history(self, token_id: str, fidelity: int = 60) -> list[dict]:
        """Get historical prices / Obtener precios históricos.

        Args:
            token_id: CLOB token ID
            fidelity: Time resolution in minutes (default 60 = hourly)
        """
        data = self._get("/prices-history", {"market": token_id, "fidelity": fidelity})
        if isinstance(data, dict) and "history" in data:
            return data["history"]
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    # User-level data / Datos a nivel de usuario
    # ------------------------------------------------------------------

    def get_user_positions(self, address: str) -> list[dict]:
        """Get user's current positions / Obtener posiciones actuales del usuario."""
        data = self._get(f"/positions", {"user": address})
        return data if isinstance(data, list) else []

    def get_user_trades(self, address: str, limit: int = 100) -> list[dict]:
        """Get user's trade history / Obtener historial de trades del usuario."""
        data = self._get(f"/trades", {"user": address, "limit": limit})
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    # Aggregated stats / Estadísticas agregadas
    # ------------------------------------------------------------------

    def get_market_volume(self, condition_id: str) -> float:
        """Get total volume for a market / Obtener volumen total de un mercado."""
        data = self._get(f"/volume", {"market": condition_id})
        if isinstance(data, dict):
            return float(data.get("volume", 0))
        return 0.0
