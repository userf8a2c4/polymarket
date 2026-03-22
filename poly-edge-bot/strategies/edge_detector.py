"""
strategies/edge_detector.py — Core edge detection engine
Motor principal de detección de ventaja (edge)

Compares model probability vs market price to find +EV opportunities.
Compara probabilidad del modelo vs precio de mercado para encontrar oportunidades +EV.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from utils.helpers import MarketInfo, Opportunity, hours_until


class EdgeDetector:
    """Detect mispriced markets / Detectar mercados mal precificados.

    The "model probability" in this version uses complementary token analysis
    and configurable custom signals. For advanced use, plug in your own model
    via custom_rules.py.

    La "probabilidad del modelo" en esta versión usa análisis de tokens
    complementarios y señales custom configurables.
    """

    def __init__(self, config: dict[str, Any]):
        edge_cfg = config.get("edge", {})
        self.min_edge = edge_cfg.get("min_edge_pct", 0.08)
        self.free_money_max_prob = edge_cfg.get("free_money_max_prob", 0.04)
        self.min_liquidity = edge_cfg.get("min_liquidity_usd", 80000)
        self.min_volume_24h = edge_cfg.get("min_volume_24h_usd", 40000)
        self.min_hours_to_resolution = edge_cfg.get("min_hours_to_resolution", 48)

    # ------------------------------------------------------------------
    # Main scan / Escaneo principal
    # ------------------------------------------------------------------

    def scan_markets(
        self,
        markets: list[MarketInfo],
        model_probs: dict[str, float] | None = None,
    ) -> list[Opportunity]:
        """Scan all markets for edge opportunities.
        Escanear todos los mercados buscando oportunidades con edge.

        Args:
            markets: Parsed market list from GammaFetcher
            model_probs: Optional dict {token_id: model_probability}.
                         If not provided, uses complementary analysis.
        """
        opportunities: list[Opportunity] = []

        for market in markets:
            # --- Pre-filters / Pre-filtros ---
            if not self._passes_filters(market):
                continue

            # Analyze each token / Analizar cada token
            for token in market.tokens:
                if not token.token_id or token.price <= 0:
                    continue

                # Get model probability / Obtener probabilidad del modelo
                if model_probs and token.token_id in model_probs:
                    model_prob = model_probs[token.token_id]
                else:
                    model_prob = self._estimate_model_prob(market, token)

                market_price = token.price

                # --- Free money detection / Detección de "dinero gratis" ---
                if self._is_free_money(market_price, market):
                    opp = Opportunity(
                        market=market,
                        side="BUY",
                        token_id=token.token_id,
                        outcome=token.outcome,
                        market_price=market_price,
                        model_prob=1.0 - market_price,
                        edge=1.0 - market_price - market_price,
                        kelly_fraction=0.0,
                        suggested_size_usd=0.0,
                        reason=f"FREE MONEY: NO at {market_price:.2%} with decent liquidity",
                    )
                    opportunities.append(opp)
                    continue

                # --- Edge calculation / Cálculo de edge ---
                edge = model_prob - market_price

                if edge >= self.min_edge:
                    opp = Opportunity(
                        market=market,
                        side="BUY",
                        token_id=token.token_id,
                        outcome=token.outcome,
                        market_price=market_price,
                        model_prob=model_prob,
                        edge=edge,
                        kelly_fraction=0.0,  # Filled by KellyCalculator
                        suggested_size_usd=0.0,
                        reason=f"Edge detected: model={model_prob:.2%} vs market={market_price:.2%} → edge={edge:.2%}",
                    )
                    opportunities.append(opp)
                    logger.info(f"EDGE: {market.question[:60]}... | {token.outcome} | edge={edge:.2%}")

                # Also check the other direction (SELL)
                sell_edge = market_price - model_prob
                if sell_edge >= self.min_edge:
                    opp = Opportunity(
                        market=market,
                        side="SELL",
                        token_id=token.token_id,
                        outcome=token.outcome,
                        market_price=market_price,
                        model_prob=model_prob,
                        edge=sell_edge,
                        kelly_fraction=0.0,
                        suggested_size_usd=0.0,
                        reason=f"SELL edge: market={market_price:.2%} vs model={model_prob:.2%} → edge={sell_edge:.2%}",
                    )
                    opportunities.append(opp)

        logger.info(f"Edge scan complete: {len(opportunities)} opportunities found")
        return opportunities

    # ------------------------------------------------------------------
    # Filters / Filtros
    # ------------------------------------------------------------------

    def _passes_filters(self, market: MarketInfo) -> bool:
        """Apply all pre-trade filters / Aplicar todos los filtros pre-trade."""
        if market.closed or not market.active:
            return False

        if market.liquidity < self.min_liquidity:
            return False

        if market.volume_24h < self.min_volume_24h:
            return False

        if market.end_date:
            hrs = hours_until(market.end_date)
            if hrs < self.min_hours_to_resolution:
                return False

        return True

    def _is_free_money(self, no_price: float, market: MarketInfo) -> bool:
        """Detect "free money" — NO tokens priced < 4% with decent liquidity.
        Detectar "dinero gratis" — tokens NO con precio < 4% y liquidez decente."""
        return (
            no_price <= self.free_money_max_prob
            and market.liquidity >= self.min_liquidity
        )

    # ------------------------------------------------------------------
    # Model estimation / Estimación del modelo
    # ------------------------------------------------------------------

    def _estimate_model_prob(self, market: MarketInfo, token: Any) -> float:
        """Estimate fair probability using complementary token analysis.
        Estimar probabilidad justa usando análisis de tokens complementarios.

        In a binary market with YES/NO, if YES is at 0.60 and NO is at 0.38,
        the "true" midpoint for YES ≈ (0.60 + (1 - 0.38)) / 2 = 0.61.
        This captures the spread inefficiency.

        For more advanced models, override this via custom_rules.py.
        """
        if len(market.tokens) == 2:
            # Binary market / Mercado binario
            prices = [t.price for t in market.tokens]
            total = sum(prices)

            if total > 0:
                # Normalized probability / Probabilidad normalizada
                idx = market.tokens.index(token)
                return prices[idx] / total
            return token.price

        # Multi-outcome: use normalized price / Multi-resultado: precio normalizado
        total = sum(t.price for t in market.tokens)
        if total > 0:
            return token.price / total
        return token.price
