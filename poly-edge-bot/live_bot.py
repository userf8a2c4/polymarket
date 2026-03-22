"""
live_bot.py — Live trading mode (REAL MONEY)
Modo de trading en vivo (DINERO REAL)

WARNING / ADVERTENCIA:
  This mode places REAL orders with REAL money from your wallet.
  Este modo coloca órdenes REALES con DINERO REAL de tu wallet.

  Only run with --mode live --confirm after thorough testing in simulator mode.
  Solo ejecutar con --mode live --confirm después de pruebas exhaustivas en simulador.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from rich.console import Console
from rich.panel import Panel

from core.client import PolymarketClient
from core.clob_trader import ClobTrader
from core.gamma_fetcher import GammaFetcher
from risk.daily_loss_limit import DailyLossLimit
from risk.liquidity_guard import LiquidityGuard
from risk.position_calculator import PositionCalculator
from risk.var_manager import PortfolioPosition, VaRManager
from strategies.custom_rules import CustomRules
from strategies.edge_detector import EdgeDetector
from strategies.kelly_fractional import KellyCalculator
from strategies.sure_bet_filter import SureBetFilter
from utils.helpers import Opportunity
from utils.notifier import notify


async def run_live(config: dict[str, Any]) -> None:
    """Run the bot in LIVE trading mode / Ejecutar en modo LIVE.

    DOUBLE CONFIRMATION: This function is only called after main.py
    verifies the --confirm flag. It also shows a 10-second countdown.
    """
    console = Console()

    # === SAFETY: Double confirmation / Doble confirmación de seguridad ===
    console.print(Panel(
        "[bold red]LIVE TRADING MODE — REAL MONEY[/bold red]\n\n"
        "This will place REAL orders on Polymarket using your wallet.\n"
        "Este modo colocará órdenes REALES en Polymarket usando tu wallet.\n\n"
        "Make sure you have tested thoroughly in simulator mode first.\n"
        "Asegúrate de haber probado exhaustivamente en modo simulador.",
        title="WARNING / ADVERTENCIA",
        border_style="red",
    ))

    console.print("[bold red]Starting in 10 seconds... Press Ctrl+C to abort[/bold red]")
    for i in range(10, 0, -1):
        console.print(f"  {i}...", end="\r")
        await asyncio.sleep(1)

    console.print("\n[bold green]LIVE MODE ACTIVATED[/bold green]\n")

    # Initialize authenticated client / Inicializar cliente autenticado
    poly_client = PolymarketClient()
    try:
        poly_client.connect_authenticated()
    except Exception as e:
        console.print(f"[red]Authentication failed: {e}[/red]")
        console.print("Check your PRIVATE_KEY and FUNDER_ADDRESS in .env")
        return

    if not poly_client.health_check():
        console.print("[red]Cannot connect to Polymarket CLOB[/red]")
        return

    trader = ClobTrader(poly_client)
    gamma = GammaFetcher()
    edge_detector = EdgeDetector(config)
    sure_bet_filter = SureBetFilter(config)
    kelly = KellyCalculator(config)
    custom_rules = CustomRules(config)
    pos_calc = PositionCalculator(config)
    var_mgr = VaRManager(config)
    liq_guard = LiquidityGuard(config)
    daily_limit = DailyLossLimit(config)

    scan_interval = config.get("scan_interval_seconds", 60)
    bankroll = config.get("risk", {}).get("max_position_usd", 100.0) * config.get("risk", {}).get("max_open_positions", 5)

    logger.info(f"Live bot started — bankroll estimate=${bankroll:.2f}")

    await notify("poly-edge-bot: LIVE MODE STARTED")

    while True:
        try:
            if not daily_limit.can_trade():
                logger.warning("Daily loss limit reached — pausing until next day")
                await notify("poly-edge-bot: Daily loss limit reached — HALTED")
                await asyncio.sleep(3600)
                continue

            # 1. Fetch and analyze / Obtener y analizar
            markets = gamma.fetch_and_parse_active(max_pages=5)
            model_probs = custom_rules.get_model_probs(markets)
            opportunities = edge_detector.scan_markets(markets, model_probs)
            opportunities = kelly.size_all(opportunities, bankroll)
            opportunities = custom_rules.filter_opportunities(opportunities)
            opportunities = custom_rules.rank_opportunities(opportunities)

            logger.info(f"Scan complete: {len(opportunities)} opportunities")

            # 2. Check existing orders / Verificar órdenes existentes
            open_orders = trader.get_open_orders()
            current_positions = len(open_orders)

            # 3. Execute top opportunities / Ejecutar mejores oportunidades
            for opp in opportunities[:2]:  # Max 2 new trades per scan in live mode
                ok, size, reason = pos_calc.validate_trade(opp, bankroll, current_positions)
                if not ok:
                    logger.debug(f"Trade rejected: {reason}")
                    continue

                # Liquidity guard / Guardia de liquidez
                size = liq_guard.adjust_size(opp.market, size)
                if size <= 0:
                    continue

                # VaR check (simplified for live) / Verificación VaR
                if not daily_limit.can_trade():
                    break

                # === EXECUTE REAL TRADE / EJECUTAR TRADE REAL ===
                logger.info(
                    f"LIVE TRADE: {opp.side} ${size:.2f} on '{opp.outcome}' "
                    f"@ {opp.market_price:.4f} — edge={opp.edge:.2%}"
                )

                # Use limit order for better fills / Usar orden límite para mejor ejecución
                price = opp.market_price
                shares = size / price if price > 0 else 0

                result = trader.place_limit_order(
                    token_id=opp.token_id,
                    side=opp.side,
                    price=price,
                    size=shares,
                    order_type="GTC",
                )

                if result.success:
                    current_positions += 1
                    msg = (
                        f"LIVE TRADE PLACED:\n"
                        f"  {opp.side} {shares:.2f} shares\n"
                        f"  '{opp.outcome}'\n"
                        f"  Price: ${price:.4f}\n"
                        f"  Size: ${size:.2f}\n"
                        f"  Edge: {opp.edge:.2%}\n"
                        f"  Order ID: {result.order_id}"
                    )
                    logger.success(msg)
                    await notify(f"poly-edge-bot TRADE:\n{msg}")
                else:
                    logger.error(f"Trade failed: {result.error}")
                    await notify(f"poly-edge-bot ERROR: Trade failed — {result.error}")

            # 4. Display status / Mostrar estado
            console.print(Panel(
                f"Time: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')} | "
                f"Open orders: {current_positions} | "
                f"Remaining budget: ${daily_limit.remaining_budget():.2f} | "
                f"Opportunities: {len(opportunities)}",
                title="Live Status",
            ))

            await asyncio.sleep(scan_interval)

        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down live bot...[/yellow]")
            console.print("[yellow]Open orders will remain active on Polymarket[/yellow]")
            console.print(daily_limit.daily_summary())
            await notify("poly-edge-bot: LIVE MODE STOPPED")
            break
        except Exception as e:
            logger.error(f"Live bot error: {e}")
            await notify(f"poly-edge-bot ERROR: {e}")
            await asyncio.sleep(30)
