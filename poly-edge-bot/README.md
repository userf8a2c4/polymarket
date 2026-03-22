# poly-edge-bot

Professional Polymarket prediction market trading bot with edge detection, fractional Kelly sizing, and comprehensive risk management.

Bot profesional de trading para mercados de predicción Polymarket con detección de ventaja, Kelly fraccionario, y gestión integral de riesgo.

---

## Features / Características

- **Edge Detection** — Identifies mispriced markets using complementary token analysis
- **Sure Bet / Arbitrage** — Detects risk-free opportunities across outcomes
- **Fractional Kelly Criterion** — Optimal position sizing with conservative multiplier
- **Risk Management** — Daily loss limits, VaR, stop-losses, liquidity guards
- **3 Execution Modes** — Read-only, Simulator, Live
- **Telegram Notifications** — Real-time alerts for opportunities and trades
- **Gamma API + CLOB API** — Full Polymarket integration via official `py-clob-client`
- **Modular Architecture** — Easy to extend with custom strategies

---

## Quick Start / Inicio Rápido

### 1. Install / Instalar

```bash
git clone <this-repo>
cd poly-edge-bot
pip install -r requirements.txt
```

### 2. Configure / Configurar

```bash
cp .env.example .env
# Edit .env with your private key and Telegram credentials
# Edita .env con tu clave privada y credenciales de Telegram
```

Get your private key from: https://reveal.polymarket.com

### 3. Run / Ejecutar

```bash
# Mode 1: Read-only — scan and display opportunities (ZERO RISK)
python main.py --mode readonly

# Mode 2: Simulator — paper trading with fake $1000
python main.py --mode sim

# Mode 3: Live trading — REAL MONEY (requires --confirm)
python main.py --mode live --confirm
```

---

## Execution Modes / Modos de Ejecución

### Read-Only (default)
- Scans Polymarket via Gamma API
- Detects edge opportunities and sure bets
- Displays results in a formatted table
- **No orders placed, no authentication needed**

### Simulator
- Paper trading with configurable fake bankroll ($1000 default)
- Simulates slippage (50 bps default)
- Full P&L tracking, win rate, drawdown stats
- Stop-loss and daily loss limit enforcement
- **No real money at risk**

### Live
- Real order placement via CLOB API
- Requires private key in `.env`
- Requires `--confirm` flag + 10-second countdown
- Limit orders (GTC) by default
- Full risk management active

---

## Project Structure / Estructura del Proyecto

```
poly-edge-bot/
├── SKILL.md                  ← Trading rules, edge doctrine, risk parameters
├── config/
│   └── config.yaml           ← Master configuration (thresholds, limits)
├── core/
│   ├── client.py             ← py-clob-client wrapper with EIP-712 auth
│   ├── gamma_fetcher.py      ← Gamma API market discovery
│   ├── clob_trader.py        ← Order execution (limit & market orders)
│   └── data_api.py           ← Data API for positions & history
├── strategies/
│   ├── edge_detector.py      ← Core edge detection engine
│   ├── sure_bet_filter.py    ← Arbitrage / sure bet scanner
│   ├── kelly_fractional.py   ← Fractional Kelly position sizing
│   └── custom_rules.py       ← YOUR custom rules go here
├── risk/
│   ├── position_calculator.py ← Position size with risk caps
│   ├── var_manager.py         ← Value at Risk calculator
│   ├── liquidity_guard.py     ← Slippage & liquidity protection
│   └── daily_loss_limit.py    ← Daily P&L tracking & halt
├── utils/
│   ├── logger.py             ← Loguru setup with rotation
│   ├── helpers.py            ← Config loader, Pydantic models
│   └── notifier.py           ← Telegram notifications
├── main.py                   ← Entry point (--mode readonly|sim|live)
├── simulator.py              ← Paper trading engine
├── live_bot.py               ← Live trading engine
├── requirements.txt
├── README.md
└── .env.example
```

---

## Configuration / Configuración

### config.yaml

All parameters are in `config/config.yaml`:

| Section  | Parameter              | Default   | Description                           |
|----------|------------------------|-----------|---------------------------------------|
| edge     | min_edge_pct           | 0.08      | Minimum edge (8%) to consider trading |
| edge     | min_liquidity_usd      | 80,000    | Minimum market liquidity              |
| edge     | min_volume_24h_usd     | 40,000    | Minimum 24h volume                    |
| edge     | min_hours_to_resolution| 48        | Skip markets resolving within 48h     |
| kelly    | alpha                  | 0.25      | Fractional Kelly multiplier           |
| kelly    | max_bet_pct            | 0.05      | Max 5% bankroll per bet               |
| risk     | daily_loss_limit_usd   | 50        | Stop trading at $50 daily loss        |
| risk     | max_position_usd       | 100       | Max single position size              |
| risk     | max_open_positions     | 5         | Max concurrent positions              |
| risk     | stop_loss_pct          | 0.15      | 15% stop-loss per trade               |

### Environment Variables (.env)

```env
PRIVATE_KEY=0x...           # Your Polygon wallet private key
FUNDER_ADDRESS=0x...        # Your Polymarket proxy address
SIGNATURE_TYPE=0            # 0=EOA, 1=Magic, 2=Browser
TELEGRAM_BOT_TOKEN=...      # Optional: Telegram alerts
TELEGRAM_CHAT_ID=...        # Optional: Telegram chat ID
```

---

## Adding Custom Strategies / Agregar Estrategias Custom

Edit `strategies/custom_rules.py`:

```python
def get_model_probs(self, markets):
    """Override market probabilities with your model."""
    probs = {}
    for market in markets:
        if "bitcoin" in market.question.lower():
            for token in market.tokens:
                # Your custom probability model here
                probs[token.token_id] = your_model.predict(market)
    return probs
```

---

## Safety / Seguridad

- **Private keys**: Only stored in `.env`, never in code or config
- **Safe first**: All trading off by default
- **Double confirmation**: Live mode requires `--confirm` + countdown
- **Daily limits**: Automatic trading halt on loss limit
- **No guaranteed profits**: This is a tool, not a money printer

---

## Dependencies / Dependencias

- `py-clob-client` — Official Polymarket CLOB client
- `httpx` — HTTP client for Gamma API
- `pydantic` — Data validation
- `loguru` — Professional logging
- `rich` — Terminal UI
- `click` — CLI framework
- `numpy` — VaR calculations
- `python-telegram-bot` — Notifications

---

## Disclaimer / Aviso Legal

This software is for educational and research purposes. Trading prediction markets involves real financial risk. The authors are not responsible for any losses. Always test with the simulator before using live mode. Never risk more than you can afford to lose.

Este software es para fines educativos y de investigación. Operar en mercados de predicción implica riesgo financiero real. Los autores no son responsables de pérdidas. Siempre prueba con el simulador antes de usar modo live. Nunca arriesgues más de lo que puedas permitirte perder.
