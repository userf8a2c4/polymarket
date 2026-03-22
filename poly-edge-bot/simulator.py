"""
simulator.py — Simulation mode (paper trading)
Modo simulación (trading con dinero ficticio)

Simulates trades without touching your wallet. Tracks performance with
full statistics. Perfect for testing strategies before going live.

Simula trades sin tocar tu wallet. Rastrea rendimiento con estadísticas
completas. Perfecto para probar estrategias antes de ir en vivo.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.gamma_fetcher import GammaFetcher
from core.client import PolymarketClient
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


@dataclass
class SimTrade:
    """A simulated trade / Un trade simulado."""
    id: int
    timestamp: str
    token_id: str
    outcome: str
    question: str
    side: str
    entry_price: float
    size_usd: float
    shares: float
    current_price: float = 0.0
    exit_price: float = 0.0
    pnl: float = 0.0
    status: str = "OPEN"  # OPEN, CLOSED, STOPPED


@dataclass
class SimPortfolio:
    """Simulated portfolio / Portafolio simulado."""
    initial_bankroll: float = 1000.0
    cash: float = 1000.0
    trades: list[SimTrade] = field(default_factory=list)
    trade_counter: int = 0
    slippage_bps: int = 50

    @property
    def open_trades(self) -> list[SimTrade]:
        return [t for t in self.trades if t.status == "OPEN"]

    @property
    def closed_trades(self) -> list[SimTrade]:
        return [t for t in self.trades if t.status != "OPEN"]

    @property
    def total_value(self) -> float:
        unrealized = sum(
            t.shares * t.current_price - t.size_usd
            for t in self.open_trades
        )
        return self.cash + sum(t.size_usd for t in self.open_trades) + unrealized

    @property
    def total_pnl(self) -> float:
        return self.total_value - self.initial_bankroll

    def execute_trade(self, opp: Opportunity, size_usd: float) -> SimTrade:
        """Simulate a trade execution / Simular una ejecución de trade."""
        self.trade_counter += 1

        # Apply slippage / Aplicar slippage
        slippage = opp.market_price * (self.slippage_bps / 10000)
        exec_price = opp.market_price + slippage if opp.side == "BUY" else opp.market_price - slippage
        exec_price = max(0.01, min(0.99, exec_price))

        shares = size_usd / exec_price

        trade = SimTrade(
            id=self.trade_counter,
            timestamp=datetime.now(timezone.utc).isoformat(),
            token_id=opp.token_id,
            outcome=opp.outcome,
            question=opp.market.question[:80],
            side=opp.side,
            entry_price=exec_price,
            size_usd=size_usd,
            shares=shares,
            current_price=opp.market_price,
        )

        self.cash -= size_usd
        self.trades.append(trade)

        logger.info(
            f"SIM TRADE #{trade.id}: {opp.side} {shares:.2f} shares of '{opp.outcome}' "
            f"@ ${exec_price:.4f} — size=${size_usd:.2f}"
        )

        return trade

    def update_prices(self, price_map: dict[str, float]) -> None:
        """Update current prices for open trades / Actualizar precios de trades abiertos."""
        for trade in self.open_trades:
            if trade.token_id in price_map:
                trade.current_price = price_map[trade.token_id]
                if trade.side == "BUY":
                    trade.pnl = (trade.current_price - trade.entry_price) * trade.shares
                else:
                    trade.pnl = (trade.entry_price - trade.current_price) * trade.shares

    def close_trade(self, trade_id: int, exit_price: float) -> float:
        """Close a simulated trade / Cerrar un trade simulado."""
        for trade in self.trades:
            if trade.id == trade_id and trade.status == "OPEN":
                trade.exit_price = exit_price
                if trade.side == "BUY":
                    trade.pnl = (exit_price - trade.entry_price) * trade.shares
                else:
                    trade.pnl = (trade.entry_price - exit_price) * trade.shares
                trade.status = "CLOSED"
                self.cash += trade.size_usd + trade.pnl
                logger.info(f"SIM CLOSE #{trade.id}: PnL=${trade.pnl:+.2f}")
                return trade.pnl
        return 0.0


async def run_simulator(config: dict[str, Any]) -> None:
    """Run the bot in simulation mode / Ejecutar el bot en modo simulación."""
    console = Console()
    console.print("[bold magenta]MODE: SIMULATOR[/bold magenta] — Paper trading with fake money\n")

    sim_cfg = config.get("simulator", {})
    initial_bankroll = sim_cfg.get("initial_bankroll", 1000.0)

    # Initialize portfolio / Inicializar portafolio
    portfolio = SimPortfolio(
        initial_bankroll=initial_bankroll,
        cash=initial_bankroll,
        slippage_bps=sim_cfg.get("slippage_bps", 50),
    )

    # Initialize components / Inicializar componentes
    poly_client = PolymarketClient()
    poly_client.connect_readonly()  # Simulator only reads market data

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

    console.print(f"  Starting bankroll: ${initial_bankroll:,.2f}")
    console.print(f"  Slippage: {portfolio.slippage_bps} bps")
    console.print(f"  Scan interval: {scan_interval}s\n")

    while True:
        try:
            if not daily_limit.can_trade():
                console.print("[red]Daily loss limit reached — waiting for next day[/red]")
                await asyncio.sleep(3600)
                continue

            console.print(f"\n[yellow]Scanning markets...[/yellow]")

            # 1. Fetch and analyze / Obtener y analizar
            markets = gamma.fetch_and_parse_active(max_pages=5)
            model_probs = custom_rules.get_model_probs(markets)
            opportunities = edge_detector.scan_markets(markets, model_probs)
            opportunities = kelly.size_all(opportunities, portfolio.cash)
            opportunities = custom_rules.filter_opportunities(opportunities)
            opportunities = custom_rules.rank_opportunities(opportunities)

            # 2. Update open positions / Actualizar posiciones abiertas
            if portfolio.open_trades:
                price_map = {}
                for trade in portfolio.open_trades:
                    try:
                        mid = poly_client.get_midpoint(trade.token_id)
                        price_map[trade.token_id] = mid
                    except Exception:
                        pass
                portfolio.update_prices(price_map)

                # Check stop-losses / Verificar stop-losses
                for trade in portfolio.open_trades:
                    sl_price = pos_calc.get_stop_loss_price(trade.entry_price, trade.side)
                    if trade.side == "BUY" and trade.current_price <= sl_price:
                        pnl = portfolio.close_trade(trade.id, trade.current_price)
                        daily_limit.record_trade(pnl)
                        console.print(f"[red]STOP-LOSS #{trade.id}: PnL=${pnl:+.2f}[/red]")
                    elif trade.side == "SELL" and trade.current_price >= sl_price:
                        pnl = portfolio.close_trade(trade.id, trade.current_price)
                        daily_limit.record_trade(pnl)
                        console.print(f"[red]STOP-LOSS #{trade.id}: PnL=${pnl:+.2f}[/red]")

            # 3. Execute new trades / Ejecutar nuevos trades
            for opp in opportunities[:3]:  # Max 3 new trades per scan
                ok, size, reason = pos_calc.validate_trade(
                    opp, portfolio.cash, len(portfolio.open_trades)
                )

                if not ok:
                    continue

                # Liquidity check / Verificación de liquidez
                size = liq_guard.adjust_size(opp.market, size)
                if size <= 0:
                    continue

                # VaR check / Verificación de VaR
                positions = [
                    PortfolioPosition(
                        token_id=t.token_id, outcome=t.outcome, question=t.question,
                        side=t.side, entry_price=t.entry_price,
                        current_price=t.current_price, size_usd=t.size_usd,
                        shares=t.shares,
                    )
                    for t in portfolio.open_trades
                ]
                if not var_mgr.is_within_limits(positions):
                    console.print("[red]VaR limit reached — skipping new trades[/red]")
                    break

                # Execute simulated trade / Ejecutar trade simulado
                trade = portfolio.execute_trade(opp, size)
                console.print(
                    f"[green]SIM TRADE #{trade.id}:[/green] {opp.side} {trade.shares:.2f} "
                    f"'{opp.outcome}' @ ${trade.entry_price:.4f} — ${size:.2f}"
                )

            # 4. Display portfolio / Mostrar portafolio
            _display_portfolio(console, portfolio, daily_limit)

            # Notify / Notificar
            if config.get("notifications", {}).get("enabled"):
                await notify(f"Sim: ${portfolio.total_value:,.2f} | PnL: ${portfolio.total_pnl:+.2f}")

            console.print(f"\n[dim]Next scan in {scan_interval}s...[/dim]")
            await asyncio.sleep(scan_interval)

        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down simulator...[/yellow]")
            _display_final_report(console, portfolio, daily_limit)
            break
        except Exception as e:
            logger.error(f"Simulator error: {e}")
            await asyncio.sleep(10)


def _display_portfolio(console: Console, portfolio: SimPortfolio, daily_limit: DailyLossLimit):
    """Display current portfolio state / Mostrar estado actual del portafolio."""
    pnl_color = "green" if portfolio.total_pnl >= 0 else "red"

    console.print(Panel(
        f"Cash: ${portfolio.cash:,.2f} | "
        f"Total: ${portfolio.total_value:,.2f} | "
        f"PnL: [{pnl_color}]${portfolio.total_pnl:+.2f}[/{pnl_color}] | "
        f"Open: {len(portfolio.open_trades)} | "
        f"Total trades: {len(portfolio.trades)}",
        title="Portfolio / Portafolio",
    ))

    if portfolio.open_trades:
        table = Table(title="Open Positions / Posiciones Abiertas")
        table.add_column("#", justify="right")
        table.add_column("Outcome", max_width=30)
        table.add_column("Side")
        table.add_column("Entry", justify="right")
        table.add_column("Current", justify="right")
        table.add_column("PnL", justify="right")

        for t in portfolio.open_trades:
            pnl_style = "green" if t.pnl >= 0 else "red"
            table.add_row(
                str(t.id), t.outcome, t.side,
                f"${t.entry_price:.4f}", f"${t.current_price:.4f}",
                f"[{pnl_style}]${t.pnl:+.2f}[/{pnl_style}]",
            )
        console.print(table)


def _display_final_report(console: Console, portfolio: SimPortfolio, daily_limit: DailyLossLimit):
    """Display final simulation report / Mostrar reporte final de simulación."""
    console.print("\n" + "=" * 60)
    console.print("[bold]SIMULATION FINAL REPORT / REPORTE FINAL[/bold]\n")
    console.print(f"  Initial bankroll: ${portfolio.initial_bankroll:,.2f}")
    console.print(f"  Final value:      ${portfolio.total_value:,.2f}")

    pnl_color = "green" if portfolio.total_pnl >= 0 else "red"
    pnl_pct = (portfolio.total_pnl / portfolio.initial_bankroll) * 100
    console.print(f"  Total PnL:        [{pnl_color}]${portfolio.total_pnl:+.2f} ({pnl_pct:+.1f}%)[/{pnl_color}]")
    console.print(f"  Total trades:     {len(portfolio.trades)}")

    closed = portfolio.closed_trades
    if closed:
        wins = [t for t in closed if t.pnl > 0]
        losses = [t for t in closed if t.pnl <= 0]
        wr = len(wins) / len(closed) * 100 if closed else 0
        console.print(f"  Win rate:         {wr:.1f}% ({len(wins)}W / {len(losses)}L)")
        if wins:
            console.print(f"  Avg win:          ${sum(t.pnl for t in wins) / len(wins):+.2f}")
        if losses:
            console.print(f"  Avg loss:         ${sum(t.pnl for t in losses) / len(losses):+.2f}")

    console.print(f"\n{daily_limit.daily_summary()}")
    console.print("=" * 60)
