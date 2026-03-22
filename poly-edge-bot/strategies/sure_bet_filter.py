"""
strategies/sure_bet_filter.py — Sure bet / arbitrage detection
Detección de apuestas seguras / arbitraje

Finds markets where the sum of best prices for all outcomes < 1.0
(guaranteed profit regardless of outcome).
Encuentra mercados donde la suma de mejores precios < 1.0
(ganancia garantizada sin importar el resultado).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from utils.helpers import MarketInfo


@dataclass
class SureBet:
    """A detected sure-bet / arbitrage opportunity."""
    market: MarketInfo
    total_cost: float         # Sum of best asks for all outcomes
    guaranteed_profit: float  # 1.0 - total_cost (per $1 wagered)
    profit_pct: float         # Profit as percentage
    legs: list[dict]          # Details for each leg


class SureBetFilter:
    """Detect arbitrage / sure-bet opportunities in prediction markets.
    Detectar oportunidades de arbitraje en mercados de predicción.

    A sure bet exists when you can buy ALL outcomes for less than $1 total.
    Una apuesta segura existe cuando puedes comprar TODOS los resultados por menos de $1.
    """

    def __init__(self, config: dict[str, Any]):
        self.min_profit_pct = config.get("sure_bet", {}).get("min_profit_pct", 0.01)  # 1%
        self.min_liquidity = config.get("edge", {}).get("min_liquidity_usd", 80000)

    def scan(self, markets: list[MarketInfo]) -> list[SureBet]:
        """Scan markets for sure-bet opportunities.
        Escanear mercados buscando apuestas seguras."""

        sure_bets: list[SureBet] = []

        for market in markets:
            if market.closed or not market.active:
                continue

            if len(market.tokens) < 2:
                continue

            if market.liquidity < self.min_liquidity:
                continue

            # Calculate total cost to buy all outcomes
            # Calcular costo total de comprar todos los resultados
            prices = [t.price for t in market.tokens if t.price > 0]

            if len(prices) != len(market.tokens):
                continue

            total_cost = sum(prices)

            if total_cost < 1.0:
                profit = 1.0 - total_cost
                profit_pct = profit / total_cost if total_cost > 0 else 0

                if profit_pct >= self.min_profit_pct:
                    legs = [
                        {
                            "token_id": t.token_id,
                            "outcome": t.outcome,
                            "price": t.price,
                        }
                        for t in market.tokens
                    ]

                    sb = SureBet(
                        market=market,
                        total_cost=total_cost,
                        guaranteed_profit=profit,
                        profit_pct=profit_pct,
                        legs=legs,
                    )
                    sure_bets.append(sb)
                    logger.info(
                        f"SURE BET: {market.question[:60]}... | "
                        f"cost={total_cost:.4f} | profit={profit_pct:.2%}"
                    )

        logger.info(f"Sure bet scan complete: {len(sure_bets)} found")
        return sure_bets

    @staticmethod
    def calculate_allocation(sure_bet: SureBet, total_budget_usd: float) -> list[dict]:
        """Calculate how much to allocate to each leg.
        Calcular cuánto asignar a cada pierna de la apuesta segura.

        In a sure bet, you want to buy equal "shares" of each outcome
        so that you receive $1 per share regardless of the result.
        """
        allocations = []
        for leg in sure_bet.legs:
            # Each leg gets proportional allocation
            amount = total_budget_usd * (leg["price"] / sure_bet.total_cost)
            allocations.append({
                **leg,
                "amount_usd": round(amount, 2),
                "shares": round(amount / leg["price"], 4) if leg["price"] > 0 else 0,
            })
        return allocations
