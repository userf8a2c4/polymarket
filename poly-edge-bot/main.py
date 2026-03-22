#!/usr/bin/env python3
"""
main.py — poly-edge-bot entry point
Punto de entrada principal del bot de trading

Usage / Uso:
    python main.py --mode readonly   # Solo analiza y muestra oportunidades
    python main.py --mode sim        # Simulador con dinero ficticio
    python main.py --mode live       # Trading real (requiere --confirm)
    python main.py --mode live --confirm  # Confirma trading real
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from loguru import logger

# Ensure project root is in path / Asegurar que el root del proyecto está en el path
sys.path.insert(0, str(Path(__file__).parent))

from utils.helpers import load_config
from utils.logger import setup_logger
from utils.notifier import notify


def print_banner():
    """Print startup banner / Imprimir banner de inicio."""
    banner = """
    ╔══════════════════════════════════════════════╗
    ║           POLY-EDGE-BOT v1.0.0              ║
    ║     Polymarket Prediction Market Bot         ║
    ║                                              ║
    ║  Modes: readonly | sim | live                ║
    ║  "Safe first" — everything off by default    ║
    ╚══════════════════════════════════════════════╝
    """
    click.echo(click.style(banner, fg="cyan"))


async def run_readonly(config: dict) -> None:
    """Read-only mode: scan and display opportunities.
    Modo solo-lectura: escanear y mostrar oportunidades."""
    from rich.console import Console
    from rich.table import Table

    from core.client import PolymarketClient
    from core.gamma_fetcher import GammaFetcher
    from strategies.custom_rules import CustomRules
    from strategies.edge_detector import EdgeDetector
    from strategies.kelly_fractional import KellyCalculator
    from strategies.sure_bet_filter import SureBetFilter

    console = Console()

    logger.info("Starting READ-ONLY mode — no trades will be placed")
    console.print("[bold green]MODE: READ-ONLY[/bold green] — Scanning markets...\n")

    # Initialize components / Inicializar componentes
    poly_client = PolymarketClient()
    poly_client.connect_readonly()

    gamma = GammaFetcher()
    edge_detector = EdgeDetector(config)
    sure_bet_filter = SureBetFilter(config)
    kelly = KellyCalculator(config)
    custom_rules = CustomRules(config)

    scan_interval = config.get("scan_interval_seconds", 60)
    bankroll = config.get("simulator", {}).get("initial_bankroll", 1000.0)

    while True:
        try:
            console.print(f"\n[yellow]Scanning markets...[/yellow]")

            # 1. Fetch markets / Obtener mercados
            markets = gamma.fetch_and_parse_active(max_pages=5)
            console.print(f"  Found {len(markets)} active markets")

            # 2. Get custom model probs / Obtener probs custom del modelo
            model_probs = custom_rules.get_model_probs(markets)

            # 3. Detect edge / Detectar edge
            opportunities = edge_detector.scan_markets(markets, model_probs)

            # 4. Size with Kelly / Dimensionar con Kelly
            opportunities = kelly.size_all(opportunities, bankroll)

            # 5. Apply custom filters / Aplicar filtros custom
            opportunities = custom_rules.filter_opportunities(opportunities)

            # 6. Rank / Rankear
            opportunities = custom_rules.rank_opportunities(opportunities)

            # 7. Check sure bets / Verificar apuestas seguras
            sure_bets = sure_bet_filter.scan(markets)

            # --- Display results / Mostrar resultados ---
            if opportunities:
                table = Table(title="Edge Opportunities / Oportunidades con Edge")
                table.add_column("Market", style="white", max_width=50)
                table.add_column("Outcome", style="cyan")
                table.add_column("Side", style="green")
                table.add_column("Market $", justify="right")
                table.add_column("Model %", justify="right")
                table.add_column("Edge", justify="right", style="bold yellow")
                table.add_column("Kelly", justify="right")
                table.add_column("Size $", justify="right", style="bold green")

                for opp in opportunities[:20]:
                    table.add_row(
                        opp.market.question[:50],
                        opp.outcome,
                        opp.side,
                        f"{opp.market_price:.2%}",
                        f"{opp.model_prob:.2%}",
                        f"{opp.edge:.2%}",
                        f"{opp.kelly_fraction:.4f}",
                        f"${opp.suggested_size_usd:.2f}",
                    )
                console.print(table)
            else:
                console.print("[dim]No edge opportunities found in this scan[/dim]")

            if sure_bets:
                console.print(f"\n[bold red]SURE BETS FOUND: {len(sure_bets)}[/bold red]")
                for sb in sure_bets:
                    console.print(
                        f"  {sb.market.question[:60]} — "
                        f"profit={sb.profit_pct:.2%} — "
                        f"cost={sb.total_cost:.4f}"
                    )

            # Notify if configured / Notificar si está configurado
            if config.get("notifications", {}).get("enabled") and opportunities:
                msg = f"poly-edge-bot: {len(opportunities)} opportunities found"
                await notify(msg)

            console.print(f"\n[dim]Next scan in {scan_interval}s... (Ctrl+C to stop)[/dim]")
            await asyncio.sleep(scan_interval)

        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
            break
        except Exception as e:
            logger.error(f"Scan error: {e}")
            await asyncio.sleep(10)


@click.command()
@click.option(
    "--mode", "-m",
    type=click.Choice(["readonly", "sim", "live"], case_sensitive=False),
    default="readonly",
    help="Execution mode / Modo de ejecución",
)
@click.option(
    "--confirm",
    is_flag=True,
    default=False,
    help="Confirm live trading (required for --mode live)",
)
@click.option(
    "--config", "-c",
    default="config/config.yaml",
    help="Path to config file / Ruta al archivo de configuración",
)
def main(mode: str, confirm: bool, config: str):
    """poly-edge-bot — Polymarket prediction market trading bot."""

    print_banner()

    # Load configuration / Cargar configuración
    try:
        cfg = load_config(config)
    except FileNotFoundError:
        click.echo(click.style(f"Config not found: {config}", fg="red"))
        sys.exit(1)

    # Setup logging / Configurar logging
    log_cfg = cfg.get("logging", {})
    setup_logger(
        level=log_cfg.get("level", "INFO"),
        log_file=log_cfg.get("file", "logs/poly-edge-bot.log"),
        rotation=log_cfg.get("rotation", "10 MB"),
        retention=log_cfg.get("retention", "7 days"),
    )

    logger.info(f"Starting poly-edge-bot in {mode.upper()} mode")

    if mode == "readonly":
        asyncio.run(run_readonly(cfg))

    elif mode == "sim":
        from simulator import run_simulator
        asyncio.run(run_simulator(cfg))

    elif mode == "live":
        if not confirm:
            click.echo(click.style(
                "\nLIVE MODE requires --confirm flag.\n"
                "This will use REAL MONEY from your wallet.\n"
                "Usage: python main.py --mode live --confirm\n",
                fg="red", bold=True,
            ))
            sys.exit(1)

        from live_bot import run_live
        asyncio.run(run_live(cfg))


if __name__ == "__main__":
    main()
