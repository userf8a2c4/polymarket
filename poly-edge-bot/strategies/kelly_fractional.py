"""
strategies/kelly_fractional.py — Fractional Kelly Criterion position sizing
Criterio de Kelly fraccionario para dimensionamiento de posiciones

The Kelly Criterion determines the optimal bet size to maximize long-term
growth of capital, given an edge and odds. We use a FRACTIONAL multiplier
(alpha) to reduce variance at the cost of slightly lower expected growth.

El Criterio de Kelly determina el tamaño óptimo de apuesta para maximizar
el crecimiento a largo plazo del capital. Usamos un multiplicador FRACCIONARIO
(alpha) para reducir varianza a costa de menor crecimiento esperado.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from utils.helpers import Opportunity


class KellyCalculator:
    """Fractional Kelly Criterion calculator / Calculadora de Kelly fraccionario.

    Formula / Fórmula:
        kelly = (p * b - q) / b
        fractional_kelly = alpha * kelly

    Where / Donde:
        p = model probability of winning
        q = 1 - p (probability of losing)
        b = odds received (payout ratio = 1/market_price - 1 for binary)
        alpha = fractional multiplier (0.25 = quarter Kelly)
    """

    def __init__(self, config: dict[str, Any]):
        kelly_cfg = config.get("kelly", {})
        self.alpha = kelly_cfg.get("alpha", 0.25)
        self.max_bet_pct = kelly_cfg.get("max_bet_pct", 0.05)

    def calculate(self, model_prob: float, market_price: float) -> float:
        """Calculate fractional Kelly fraction / Calcular fracción de Kelly fraccionario.

        Args:
            model_prob: Our estimated probability (0 to 1)
            market_price: Current market price (0 to 1)

        Returns:
            Fraction of bankroll to bet (0 to max_bet_pct)
        """
        if market_price <= 0 or market_price >= 1 or model_prob <= 0 or model_prob >= 1:
            return 0.0

        p = model_prob
        q = 1.0 - p

        # Binary market odds: if you buy at price, you get 1/price payout
        # b = net odds = (1 - price) / price
        b = (1.0 - market_price) / market_price

        if b <= 0:
            return 0.0

        # Full Kelly / Kelly completo
        full_kelly = (p * b - q) / b

        if full_kelly <= 0:
            return 0.0  # No edge, don't bet / Sin edge, no apostar

        # Fractional Kelly / Kelly fraccionario
        frac_kelly = self.alpha * full_kelly

        # Cap at max_bet_pct / Limitar a max_bet_pct
        capped = min(frac_kelly, self.max_bet_pct)

        return round(capped, 6)

    def size_opportunity(self, opp: Opportunity, bankroll: float) -> Opportunity:
        """Calculate Kelly fraction and suggested size for an opportunity.
        Calcular fracción de Kelly y tamaño sugerido para una oportunidad."""

        kelly_f = self.calculate(opp.model_prob, opp.market_price)
        suggested_usd = round(bankroll * kelly_f, 2)

        # Return updated opportunity / Retornar oportunidad actualizada
        return opp.model_copy(update={
            "kelly_fraction": kelly_f,
            "suggested_size_usd": suggested_usd,
        })

    def size_all(self, opportunities: list[Opportunity], bankroll: float) -> list[Opportunity]:
        """Size all opportunities / Dimensionar todas las oportunidades."""
        sized = []
        for opp in opportunities:
            sized_opp = self.size_opportunity(opp, bankroll)
            if sized_opp.kelly_fraction > 0:
                sized.append(sized_opp)
                logger.debug(
                    f"Kelly: {opp.outcome} | kelly={sized_opp.kelly_fraction:.4f} | "
                    f"size=${sized_opp.suggested_size_usd:.2f}"
                )

        logger.info(f"Kelly sizing: {len(sized)}/{len(opportunities)} opportunities have positive Kelly")
        return sized
