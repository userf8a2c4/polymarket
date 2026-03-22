"""
core/gamma_fetcher.py — Gamma API market discovery
Descubrimiento de mercados via Gamma API de Polymarket

Gamma provides enriched metadata: categories, volume, liquidity, resolution dates.
Gamma provee metadata enriquecida: categorías, volumen, liquidez, fechas de resolución.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from loguru import logger

from utils.helpers import MarketInfo, MarketToken, safe_float


class GammaFetcher:
    """Fetch and parse market data from Polymarket Gamma API.
    Obtener y parsear datos de mercados de la API Gamma."""

    BASE_URL = "https://gamma-api.polymarket.com"

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv("GAMMA_HOST", self.BASE_URL)

    # ------------------------------------------------------------------
    # Raw fetchers / Fetchers crudos
    # ------------------------------------------------------------------

    def _get(self, endpoint: str, params: Optional[dict] = None) -> list[dict]:
        """HTTP GET with error handling / GET HTTP con manejo de errores."""
        url = f"{self.base_url}{endpoint}"
        try:
            resp = httpx.get(url, params=params, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            # Gamma can return a list or a dict with a list
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            return [data] if isinstance(data, dict) else []
        except httpx.HTTPStatusError as e:
            logger.error(f"Gamma API HTTP error: {e.response.status_code} — {url}")
            return []
        except Exception as e:
            logger.error(f"Gamma API request failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Market discovery / Descubrimiento de mercados
    # ------------------------------------------------------------------

    def get_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active: bool = True,
        closed: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch markets with filters / Obtener mercados con filtros."""
        params = {
            "limit": limit,
            "offset": offset,
            "active": str(active).lower(),
            "closed": str(closed).lower(),
        }
        return self._get("/markets", params)

    def get_all_active_markets(self, max_pages: int = 10) -> list[dict[str, Any]]:
        """Paginate through all active markets / Paginar todos los mercados activos."""
        all_markets: list[dict] = []
        limit = 100

        for page in range(max_pages):
            batch = self.get_markets(limit=limit, offset=page * limit)
            if not batch:
                break
            all_markets.extend(batch)
            if len(batch) < limit:
                break

        logger.info(f"Fetched {len(all_markets)} active markets from Gamma")
        return all_markets

    def get_events(self, limit: int = 100, active: bool = True) -> list[dict]:
        """Fetch events / Obtener eventos."""
        params = {"limit": limit, "active": str(active).lower()}
        return self._get("/events", params)

    def get_market_by_id(self, condition_id: str) -> Optional[dict]:
        """Fetch a single market / Obtener un mercado individual."""
        results = self._get(f"/markets/{condition_id}")
        return results[0] if results else None

    # ------------------------------------------------------------------
    # Parsing / Parseo
    # ------------------------------------------------------------------

    def parse_market(self, raw: dict[str, Any]) -> MarketInfo:
        """Parse raw Gamma market dict into MarketInfo.
        Parsear dict crudo de Gamma a MarketInfo."""

        tokens = []
        clob_token_ids = raw.get("clobTokenIds") or raw.get("clob_token_ids") or ""
        outcomes = raw.get("outcomes") or raw.get("groupItemTitle") or ""
        outcome_prices = raw.get("outcomePrices") or raw.get("outcome_prices") or ""

        # Parse token IDs and outcomes
        if isinstance(clob_token_ids, str):
            try:
                import json
                token_id_list = json.loads(clob_token_ids) if clob_token_ids.startswith("[") else [clob_token_ids]
            except Exception:
                token_id_list = [clob_token_ids] if clob_token_ids else []
        else:
            token_id_list = list(clob_token_ids)

        if isinstance(outcomes, str):
            try:
                import json
                outcome_list = json.loads(outcomes) if outcomes.startswith("[") else [outcomes]
            except Exception:
                outcome_list = [outcomes] if outcomes else []
        else:
            outcome_list = list(outcomes)

        if isinstance(outcome_prices, str):
            try:
                import json
                price_list = json.loads(outcome_prices) if outcome_prices.startswith("[") else [safe_float(outcome_prices)]
            except Exception:
                price_list = []
        else:
            price_list = [safe_float(p) for p in outcome_prices] if outcome_prices else []

        for i, tid in enumerate(token_id_list):
            outcome_name = outcome_list[i] if i < len(outcome_list) else f"Outcome_{i}"
            price = price_list[i] if i < len(price_list) else 0.0
            tokens.append(MarketToken(token_id=str(tid), outcome=str(outcome_name), price=safe_float(price)))

        return MarketInfo(
            condition_id=str(raw.get("conditionId") or raw.get("condition_id") or ""),
            question=str(raw.get("question") or raw.get("title") or ""),
            slug=str(raw.get("slug") or ""),
            category=str(raw.get("category") or ""),
            end_date=str(raw.get("endDate") or raw.get("end_date_iso") or ""),
            active=bool(raw.get("active", True)),
            closed=bool(raw.get("closed", False)),
            liquidity=safe_float(raw.get("liquidity")),
            volume=safe_float(raw.get("volume")),
            volume_24h=safe_float(raw.get("volume24hr") or raw.get("volume_num")),
            tokens=tokens,
        )

    def fetch_and_parse_active(self, max_pages: int = 10) -> list[MarketInfo]:
        """Fetch all active markets and parse them / Obtener y parsear mercados activos."""
        raw_markets = self.get_all_active_markets(max_pages=max_pages)
        parsed = [self.parse_market(m) for m in raw_markets]
        logger.info(f"Parsed {len(parsed)} markets")
        return parsed
