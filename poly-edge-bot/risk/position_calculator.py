"""
risk/position_calculator.py — Position size calculator with risk limits
Calculadora de tamaño de posición con límites de riesgo

Ensures no single position exceeds configured limits.
Asegura que ninguna posición individual exceda los límites configurados.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from utils.helpers import Opportunity


class PositionCalculator:
    """Calculate safe position sizes / Calcular tamaños de posición seguros.

    Applies multiple caps:
    1. Kelly-suggested size (from strategies)
    2. Max position USD (absolute cap)
    3. Max % of bankroll per trade
    4. Max open positions limit
    """

    def __init__(self, config: dict[str, Any]):
        risk_cfg = config.get("risk", {})
        self.max_position_usd = risk_cfg.get("max_position_usd", 100.0)
        self.max_open_positions = risk_cfg.get("max_open_positions", 5)
        self.stop_loss_pct = risk_cfg.get("stop_loss_pct", 0.15)

    def calculate_size(
        self,
        opp: Opportunity,
        bankroll: float,
        current_open_positions: int = 0,
    ) -> float:
        """Calculate final position size with all risk caps applied.
        Calcular tamaño final de posición con todos los límites de riesgo.

        Returns 0.0 if the trade should be skipped.
        """
        # Check position count limit / Verificar límite de posiciones
        if current_open_positions >= self.max_open_positions:
            logger.warning(f"Max open positions reached ({self.max_open_positions})")
            return 0.0

        # Start with Kelly suggestion / Comenzar con sugerencia de Kelly
        size = opp.suggested_size_usd

        # Cap at max position / Limitar a posición máxima
        if size > self.max_position_usd:
            logger.debug(f"Position capped: ${size:.2f} → ${self.max_position_usd:.2f}")
            size = self.max_position_usd

        # Minimum viable size / Tamaño mínimo viable
        if size < 1.0:
            logger.debug(f"Position too small: ${size:.2f} — skipping")
            return 0.0

        # Don't exceed bankroll / No exceder bankroll
        if size > bankroll * 0.95:
            size = bankroll * 0.95
            logger.debug(f"Position capped to 95% of bankroll: ${size:.2f}")

        return round(size, 2)

    def get_stop_loss_price(self, entry_price: float, side: str) -> float:
        """Calculate stop-loss price / Calcular precio de stop-loss.

        For BUY: stop if price drops by stop_loss_pct
        For SELL: stop if price rises by stop_loss_pct
        """
        if side.upper() == "BUY":
            return round(entry_price * (1.0 - self.stop_loss_pct), 4)
        else:
            return round(entry_price * (1.0 + self.stop_loss_pct), 4)

    def validate_trade(
        self,
        opp: Opportunity,
        bankroll: float,
        current_open_positions: int = 0,
    ) -> tuple[bool, float, str]:
        """Validate and size a trade. Returns (ok, size, reason).
        Validar y dimensionar un trade. Retorna (ok, tamaño, razón)."""

        size = self.calculate_size(opp, bankroll, current_open_positions)

        if size <= 0:
            return False, 0.0, "Position size is zero or negative after risk caps"

        if opp.edge < 0.01:
            return False, 0.0, f"Edge too small: {opp.edge:.4f}"

        return True, size, "OK"
