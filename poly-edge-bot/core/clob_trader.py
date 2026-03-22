"""
core/clob_trader.py — Order execution via CLOB API
Ejecución de órdenes via la API CLOB de Polymarket

Uses py-clob-client for signed order placement (EIP-712).
Usa py-clob-client para colocación de órdenes firmadas (EIP-712).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger
from py_clob_client.clob_types import MarketOrderArgs, OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

from core.client import PolymarketClient


@dataclass
class TradeResult:
    """Result of a trade execution / Resultado de una ejecución de trade."""
    success: bool
    order_id: str = ""
    status: str = ""
    side: str = ""
    token_id: str = ""
    price: float = 0.0
    size: float = 0.0
    amount_usd: float = 0.0
    error: str = ""
    raw_response: Optional[dict] = None


class ClobTrader:
    """Execute trades on Polymarket CLOB / Ejecutar trades en el CLOB de Polymarket.

    SAFETY: All methods check authentication before attempting trades.
    SEGURIDAD: Todos los métodos verifican autenticación antes de intentar trades.
    """

    def __init__(self, poly_client: PolymarketClient):
        self.poly_client = poly_client

    def _require_auth(self) -> None:
        """Ensure client is authenticated / Asegurar que el cliente está autenticado."""
        if not self.poly_client.is_authenticated:
            raise RuntimeError(
                "Cannot trade without authentication. "
                "Call connect_authenticated() first."
            )

    # ------------------------------------------------------------------
    # Limit orders / Órdenes límite
    # ------------------------------------------------------------------

    def place_limit_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
        order_type: str = "GTC",
    ) -> TradeResult:
        """Place a limit order / Colocar una orden límite.

        Args:
            token_id: CLOB token ID for the outcome
            side: "BUY" or "SELL"
            price: Limit price (0.01 to 0.99)
            size: Number of shares
            order_type: "GTC" (default) or "GTD"
        """
        self._require_auth()

        try:
            order_side = BUY if side.upper() == "BUY" else SELL
            ot = OrderType.GTC if order_type == "GTC" else OrderType.GTC

            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=order_side,
            )

            logger.info(f"Creating limit order: {side} {size} shares @ ${price} — token={token_id[:16]}...")
            signed_order = self.poly_client.client.create_order(order_args)
            response = self.poly_client.client.post_order(signed_order, ot)

            order_id = ""
            if isinstance(response, dict):
                order_id = response.get("orderID", response.get("id", ""))

            logger.success(f"Limit order placed: {order_id}")

            return TradeResult(
                success=True,
                order_id=str(order_id),
                status="PLACED",
                side=side.upper(),
                token_id=token_id,
                price=price,
                size=size,
                amount_usd=price * size,
                raw_response=response if isinstance(response, dict) else {"response": str(response)},
            )

        except Exception as e:
            logger.error(f"Limit order failed: {e}")
            return TradeResult(success=False, error=str(e), token_id=token_id, side=side)

    # ------------------------------------------------------------------
    # Market orders / Órdenes de mercado
    # ------------------------------------------------------------------

    def place_market_order(
        self,
        token_id: str,
        side: str,
        amount_usd: float,
    ) -> TradeResult:
        """Place a market order (Fill-or-Kill) / Colocar orden de mercado (FOK).

        Args:
            token_id: CLOB token ID
            side: "BUY" or "SELL"
            amount_usd: Amount in USD to spend (BUY) or shares to sell (SELL)
        """
        self._require_auth()

        try:
            order_side = BUY if side.upper() == "BUY" else SELL

            mo = MarketOrderArgs(
                token_id=token_id,
                amount=amount_usd,
                side=order_side,
                order_type=OrderType.FOK,
            )

            logger.info(f"Creating market order: {side} ${amount_usd} — token={token_id[:16]}...")
            signed_order = self.poly_client.client.create_market_order(mo)
            response = self.poly_client.client.post_order(signed_order, OrderType.FOK)

            order_id = ""
            if isinstance(response, dict):
                order_id = response.get("orderID", response.get("id", ""))

            logger.success(f"Market order placed: {order_id}")

            return TradeResult(
                success=True,
                order_id=str(order_id),
                status="FILLED",
                side=side.upper(),
                token_id=token_id,
                amount_usd=amount_usd,
                raw_response=response if isinstance(response, dict) else {"response": str(response)},
            )

        except Exception as e:
            logger.error(f"Market order failed: {e}")
            return TradeResult(success=False, error=str(e), token_id=token_id, side=side)

    # ------------------------------------------------------------------
    # Order management / Gestión de órdenes
    # ------------------------------------------------------------------

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a specific order / Cancelar una orden específica."""
        self._require_auth()
        try:
            self.poly_client.client.cancel(order_id)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return False

    def cancel_all_orders(self) -> bool:
        """Cancel all open orders / Cancelar todas las órdenes abiertas."""
        self._require_auth()
        try:
            self.poly_client.client.cancel_all()
            logger.info("All orders cancelled")
            return True
        except Exception as e:
            logger.error(f"Cancel all failed: {e}")
            return False

    def get_open_orders(self) -> list[dict[str, Any]]:
        """Get all open orders / Obtener todas las órdenes abiertas."""
        self._require_auth()
        try:
            from py_clob_client.clob_types import OpenOrderParams
            orders = self.poly_client.client.get_orders(OpenOrderParams())
            return orders if isinstance(orders, list) else []
        except Exception as e:
            logger.error(f"Get orders failed: {e}")
            return []
