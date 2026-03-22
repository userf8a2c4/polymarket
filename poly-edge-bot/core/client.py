"""
core/client.py — Polymarket CLOB client wrapper
Wrapper del cliente oficial py-clob-client con autenticación EIP-712

SECURITY WARNING / ADVERTENCIA DE SEGURIDAD:
  Your private key controls your funds. NEVER share it or commit it.
  Tu clave privada controla tus fondos. NUNCA la compartas ni la subas.
"""

from __future__ import annotations

import os
from typing import Optional

from loguru import logger
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BookParams


class PolymarketClient:
    """Unified Polymarket CLOB client with auth management.
    Cliente unificado con gestión de autenticación."""

    def __init__(
        self,
        host: str = "",
        private_key: str = "",
        chain_id: int = 137,
        signature_type: int = 0,
        funder: str = "",
    ):
        self.host = host or os.getenv("CLOB_HOST", "https://clob.polymarket.com")
        self.private_key = private_key or os.getenv("PRIVATE_KEY", "")
        self.chain_id = chain_id
        self.signature_type = int(os.getenv("SIGNATURE_TYPE", str(signature_type)))
        self.funder = funder or os.getenv("FUNDER_ADDRESS", "")
        self._client: Optional[ClobClient] = None
        self._authenticated = False

    # ------------------------------------------------------------------
    # Initialization / Inicialización
    # ------------------------------------------------------------------

    def connect_readonly(self) -> ClobClient:
        """Create a read-only client (no private key needed).
        Crear cliente de solo lectura (sin clave privada)."""
        self._client = ClobClient(self.host)
        self._authenticated = False
        logger.info("Connected to CLOB (read-only)")
        return self._client

    def connect_authenticated(self) -> ClobClient:
        """Create an authenticated client with EIP-712 credentials.
        Crear cliente autenticado con credenciales EIP-712.

        WARNING: This uses your private key to derive API credentials.
        ADVERTENCIA: Esto usa tu clave privada para derivar credenciales API.
        """
        if not self.private_key:
            raise ValueError(
                "PRIVATE_KEY is required for authenticated mode. "
                "Set it in .env or pass it directly. "
                "Get it from https://reveal.polymarket.com"
            )

        kwargs = {
            "host": self.host,
            "key": self.private_key,
            "chain_id": self.chain_id,
        }

        if self.funder:
            kwargs["funder"] = self.funder
            kwargs["signature_type"] = self.signature_type

        self._client = ClobClient(**kwargs)

        # Derive L2 API credentials / Derivar credenciales API L2
        logger.info("Deriving API credentials (EIP-712 signature)...")
        creds = self._client.create_or_derive_api_creds()
        self._client.set_api_creds(creds)
        self._authenticated = True
        logger.success("Authenticated with Polymarket CLOB")

        return self._client

    # ------------------------------------------------------------------
    # Properties / Propiedades
    # ------------------------------------------------------------------

    @property
    def client(self) -> ClobClient:
        """Get underlying ClobClient / Obtener ClobClient subyacente."""
        if self._client is None:
            raise RuntimeError("Client not connected. Call connect_readonly() or connect_authenticated()")
        return self._client

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    # ------------------------------------------------------------------
    # Market data shortcuts / Atajos de datos de mercado
    # ------------------------------------------------------------------

    def get_midpoint(self, token_id: str) -> float:
        """Get mid-market price / Obtener precio medio."""
        resp = self.client.get_midpoint(token_id)
        return float(resp.get("mid", 0))

    def get_price(self, token_id: str, side: str = "BUY") -> float:
        """Get best price for a side / Obtener mejor precio para un lado."""
        resp = self.client.get_price(token_id, side)
        return float(resp.get("price", 0))

    def get_order_book(self, token_id: str) -> dict:
        """Get full order book / Obtener libro de órdenes completo."""
        return self.client.get_order_book(token_id)

    def get_order_books_batch(self, token_ids: list[str]) -> list[dict]:
        """Batch fetch order books / Obtener libros de órdenes en lote."""
        params = [BookParams(token_id=tid) for tid in token_ids]
        return self.client.get_order_books(params)

    def get_last_trade_price(self, token_id: str) -> float:
        """Last trade price / Último precio negociado."""
        resp = self.client.get_last_trade_price(token_id)
        return float(resp.get("price", 0))

    # ------------------------------------------------------------------
    # Health / Salud
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """Check server connectivity / Verificar conectividad."""
        try:
            resp = self.client.get_ok()
            return resp == "OK"
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
