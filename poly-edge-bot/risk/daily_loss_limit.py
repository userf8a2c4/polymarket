"""
risk/daily_loss_limit.py — Daily loss limit tracker
Rastreador de límite de pérdida diaria

Tracks cumulative daily P&L and halts trading when limit is hit.
Rastrea el PnL diario acumulado y detiene el trading cuando se alcanza el límite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from loguru import logger


@dataclass
class DailyPnL:
    """Daily P&L tracking record / Registro de tracking de PnL diario."""
    date: str
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    trades_count: int = 0
    wins: int = 0
    losses: int = 0
    largest_win: float = 0.0
    largest_loss: float = 0.0


class DailyLossLimit:
    """Track and enforce daily loss limits / Rastrear y aplicar límites de pérdida diaria.

    SAFETY FEATURE / FEATURE DE SEGURIDAD:
    When the daily loss limit is hit, ALL trading is halted until the next day.
    Cuando se alcanza el límite de pérdida diaria, TODO el trading se detiene hasta el día siguiente.
    """

    def __init__(self, config: dict[str, Any]):
        risk_cfg = config.get("risk", {})
        self.limit_usd = risk_cfg.get("daily_loss_limit_usd", 50.0)
        self._records: dict[str, DailyPnL] = {}
        self._halted = False

    @property
    def today_key(self) -> str:
        """Today's date key / Clave de fecha de hoy."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    @property
    def today(self) -> DailyPnL:
        """Get or create today's record / Obtener o crear registro de hoy."""
        key = self.today_key
        if key not in self._records:
            self._records[key] = DailyPnL(date=key)
            self._halted = False  # Reset halt on new day / Resetear halt en nuevo día
        return self._records[key]

    # ------------------------------------------------------------------
    # Recording / Registro
    # ------------------------------------------------------------------

    def record_trade(self, pnl: float) -> None:
        """Record a completed trade's P&L / Registrar PnL de un trade completado."""
        rec = self.today
        rec.realized_pnl += pnl
        rec.trades_count += 1

        if pnl >= 0:
            rec.wins += 1
            rec.largest_win = max(rec.largest_win, pnl)
        else:
            rec.losses += 1
            rec.largest_loss = min(rec.largest_loss, pnl)

        logger.info(
            f"Trade recorded: PnL=${pnl:+.2f} | "
            f"Daily total=${rec.realized_pnl:+.2f} | "
            f"Trades={rec.trades_count}"
        )

        # Check limit / Verificar límite
        if rec.realized_pnl <= -self.limit_usd:
            self._halted = True
            logger.error(
                f"DAILY LOSS LIMIT HIT: ${rec.realized_pnl:.2f} <= -${self.limit_usd:.2f}. "
                f"ALL TRADING HALTED until next day."
            )

    def update_unrealized(self, unrealized_pnl: float) -> None:
        """Update unrealized P&L / Actualizar PnL no realizado."""
        self.today.unrealized_pnl = unrealized_pnl

    # ------------------------------------------------------------------
    # Checks / Verificaciones
    # ------------------------------------------------------------------

    def can_trade(self) -> bool:
        """Check if trading is allowed / Verificar si el trading está permitido."""
        if self._halted:
            logger.warning("Trading HALTED — daily loss limit reached")
            return False

        rec = self.today
        remaining = self.limit_usd + rec.realized_pnl
        if remaining <= 0:
            self._halted = True
            return False

        return True

    def remaining_budget(self) -> float:
        """How much more we can lose today / Cuánto más podemos perder hoy."""
        return max(0, self.limit_usd + self.today.realized_pnl)

    # ------------------------------------------------------------------
    # Reporting / Reportes
    # ------------------------------------------------------------------

    def daily_summary(self) -> str:
        """Generate daily summary / Generar resumen diario."""
        rec = self.today
        win_rate = (rec.wins / rec.trades_count * 100) if rec.trades_count > 0 else 0

        return (
            f"=== Daily Summary ({rec.date}) ===\n"
            f"Realized PnL:   ${rec.realized_pnl:+.2f}\n"
            f"Unrealized PnL: ${rec.unrealized_pnl:+.2f}\n"
            f"Trades:         {rec.trades_count} (W:{rec.wins} / L:{rec.losses})\n"
            f"Win Rate:       {win_rate:.1f}%\n"
            f"Largest Win:    ${rec.largest_win:+.2f}\n"
            f"Largest Loss:   ${rec.largest_loss:+.2f}\n"
            f"Remaining:      ${self.remaining_budget():.2f} of ${self.limit_usd:.2f}\n"
            f"Status:         {'HALTED' if self._halted else 'ACTIVE'}"
        )

    def get_history(self) -> list[DailyPnL]:
        """Get all daily records / Obtener todos los registros diarios."""
        return list(self._records.values())
