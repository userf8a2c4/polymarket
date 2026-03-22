"""
risk/liquidity_guard.py — Liquidity guard and slippage estimator
Guardia de liquidez y estimador de deslizamiento (slippage)

Prevents trading in thin markets where execution would move the price.
Previene operar en mercados delgados donde la ejecución movería el precio.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from utils.helpers import MarketInfo


@dataclass
class LiquidityCheck:
    """Result of a liquidity check / Resultado de un chequeo de liquidez."""
    ok: bool
    market_liquidity: float
    estimated_slippage_bps: int  # Basis points of expected slippage
    max_safe_size_usd: float    # Max order size without excessive slippage
    reason: str = ""


class LiquidityGuard:
    """Guard against trading in illiquid markets.
    Guardia contra operar en mercados ilíquidos.

    Rules / Reglas:
    1. Market must have min liquidity / Mercado debe tener liquidez mínima
    2. Order size must be < X% of total liquidity / Orden debe ser < X% de liquidez total
    3. Estimated slippage must be below threshold / Slippage estimado debe estar bajo umbral
    """

    def __init__(self, config: dict[str, Any]):
        edge_cfg = config.get("edge", {})
        self.min_liquidity = edge_cfg.get("min_liquidity_usd", 80000)
        self.max_order_pct_of_liquidity = 0.02  # Max 2% of total liquidity per order
        self.max_slippage_bps = 100  # Max 100 bps (1%) slippage

    def check(self, market: MarketInfo, order_size_usd: float) -> LiquidityCheck:
        """Check if a trade is safe from liquidity perspective.
        Verificar si un trade es seguro desde la perspectiva de liquidez."""

        # Minimum liquidity check / Verificación de liquidez mínima
        if market.liquidity < self.min_liquidity:
            return LiquidityCheck(
                ok=False,
                market_liquidity=market.liquidity,
                estimated_slippage_bps=0,
                max_safe_size_usd=0.0,
                reason=f"Liquidity ${market.liquidity:,.0f} < minimum ${self.min_liquidity:,.0f}",
            )

        # Order size vs liquidity / Tamaño de orden vs liquidez
        max_safe_size = market.liquidity * self.max_order_pct_of_liquidity

        # Slippage estimation (simplified model)
        # Estimación de slippage (modelo simplificado)
        # Slippage ≈ (order_size / liquidity) * 10000 bps
        if market.liquidity > 0:
            estimated_slippage = int((order_size_usd / market.liquidity) * 10000)
        else:
            estimated_slippage = 9999

        ok = (
            order_size_usd <= max_safe_size
            and estimated_slippage <= self.max_slippage_bps
        )

        reason = ""
        if not ok:
            if order_size_usd > max_safe_size:
                reason = (
                    f"Order ${order_size_usd:.2f} exceeds safe size ${max_safe_size:.2f} "
                    f"({self.max_order_pct_of_liquidity:.0%} of liquidity)"
                )
            else:
                reason = f"Estimated slippage {estimated_slippage}bps > max {self.max_slippage_bps}bps"

        return LiquidityCheck(
            ok=ok,
            market_liquidity=market.liquidity,
            estimated_slippage_bps=estimated_slippage,
            max_safe_size_usd=round(max_safe_size, 2),
            reason=reason,
        )

    def adjust_size(self, market: MarketInfo, desired_size_usd: float) -> float:
        """Adjust order size down to safe level if needed.
        Ajustar tamaño de orden hacia abajo a nivel seguro si es necesario."""
        check = self.check(market, desired_size_usd)

        if check.ok:
            return desired_size_usd

        safe_size = min(desired_size_usd, check.max_safe_size_usd)
        if safe_size < 1.0:
            return 0.0

        logger.debug(
            f"LiquidityGuard: Adjusted ${desired_size_usd:.2f} → ${safe_size:.2f} "
            f"(liquidity=${market.liquidity:,.0f})"
        )
        return round(safe_size, 2)
