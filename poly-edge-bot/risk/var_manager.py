"""
risk/var_manager.py — Value at Risk (VaR) manager
Gestor de Valor en Riesgo (VaR)

Estimates portfolio risk using historical simulation.
Estima el riesgo del portafolio usando simulación histórica.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from loguru import logger


@dataclass
class PortfolioPosition:
    """A single position in the portfolio / Una posición en el portafolio."""
    token_id: str
    outcome: str
    question: str
    side: str  # BUY or SELL
    entry_price: float
    current_price: float
    size_usd: float
    shares: float
    unrealized_pnl: float = 0.0


@dataclass
class VaRReport:
    """VaR calculation report / Reporte de cálculo de VaR."""
    var_usd: float          # Value at Risk in USD
    confidence: float       # Confidence level (e.g. 0.95)
    horizon_hours: int      # Time horizon
    total_exposure: float   # Total portfolio exposure
    positions_count: int
    max_single_loss: float  # Worst single position loss
    warnings: list[str] = field(default_factory=list)


class VaRManager:
    """Portfolio Value at Risk manager / Gestor de VaR del portafolio.

    Uses parametric VaR with assumed volatility for prediction markets.
    Usa VaR paramétrico con volatilidad asumida para mercados de predicción.

    In prediction markets, prices are bounded [0, 1], so we use a
    simplified model where max loss = position size (price goes to 0).
    """

    def __init__(self, config: dict[str, Any]):
        risk_cfg = config.get("risk", {})
        self.confidence = risk_cfg.get("var_confidence", 0.95)
        self.horizon_hours = risk_cfg.get("var_horizon_hours", 24)
        self.daily_loss_limit = risk_cfg.get("daily_loss_limit_usd", 50.0)

    def calculate_var(self, positions: list[PortfolioPosition]) -> VaRReport:
        """Calculate portfolio VaR / Calcular VaR del portafolio.

        For prediction markets, we estimate VaR as:
        - Each position has max loss = invested amount
        - Expected loss depends on how far price is from edge
        - We use a simple model: VaR ≈ sum of (position_size * loss_probability)
        """
        if not positions:
            return VaRReport(
                var_usd=0.0,
                confidence=self.confidence,
                horizon_hours=self.horizon_hours,
                total_exposure=0.0,
                positions_count=0,
                max_single_loss=0.0,
            )

        total_exposure = sum(p.size_usd for p in positions)
        position_losses = []

        for pos in positions:
            # Max loss for a BUY position = entry_price * shares
            # Max loss for a SELL position = (1 - entry_price) * shares
            if pos.side == "BUY":
                max_loss = pos.entry_price * pos.shares
            else:
                max_loss = (1.0 - pos.entry_price) * pos.shares
            position_losses.append(max_loss)

        # Parametric VaR using normal approximation
        # For prediction markets, assume ~20% daily volatility per position
        assumed_daily_vol = 0.20
        position_vars = [loss * assumed_daily_vol for loss in position_losses]

        # Portfolio VaR (assuming moderate correlation ~0.3)
        # VaR = sqrt(sum(var_i^2) + 2 * rho * sum_pairs(var_i * var_j))
        n = len(position_vars)
        rho = 0.3

        var_squared = sum(v ** 2 for v in position_vars)
        cross_terms = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                cross_terms += position_vars[i] * position_vars[j]

        portfolio_var = np.sqrt(var_squared + 2 * rho * cross_terms)

        # Scale to confidence level / Escalar al nivel de confianza
        z_score = {0.90: 1.282, 0.95: 1.645, 0.99: 2.326}.get(self.confidence, 1.645)
        var_usd = round(portfolio_var * z_score, 2)

        warnings = []
        if var_usd > self.daily_loss_limit:
            warnings.append(
                f"VaR (${var_usd}) exceeds daily loss limit (${self.daily_loss_limit})"
            )
        if total_exposure > self.daily_loss_limit * 5:
            warnings.append(
                f"Total exposure (${total_exposure:.2f}) is >5x daily loss limit"
            )

        report = VaRReport(
            var_usd=var_usd,
            confidence=self.confidence,
            horizon_hours=self.horizon_hours,
            total_exposure=total_exposure,
            positions_count=len(positions),
            max_single_loss=round(max(position_losses) if position_losses else 0, 2),
            warnings=warnings,
        )

        if warnings:
            for w in warnings:
                logger.warning(f"VaR WARNING: {w}")

        return report

    def is_within_limits(self, positions: list[PortfolioPosition]) -> bool:
        """Check if current risk is within limits / Verificar si el riesgo está dentro de límites."""
        report = self.calculate_var(positions)
        return report.var_usd <= self.daily_loss_limit
