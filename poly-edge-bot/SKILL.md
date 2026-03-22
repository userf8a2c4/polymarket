# SKILL.md — poly-edge-bot Trading Rules & Edge Doctrine

> "The market is wrong often enough to make you rich, but right often enough to make you humble."
> "El mercado se equivoca lo suficiente para hacerte rico, pero acierta lo suficiente para hacerte humilde."

---

## 1. Core Philosophy / Filosofía Central

- **Safe first**: Everything is OFF by default. No trade executes unless explicitly enabled.
- **Edge or nothing**: If there's no quantifiable edge, there's no trade.
- **Small and consistent**: Fractional Kelly ensures we never overbet.
- **Survive first, profit second**: Risk management always overrides opportunity.

---

## 2. Edge Detection Rules / Reglas de Detección de Ventaja

### 2.1 Minimum Edge Threshold
- **Rule**: `model_probability - market_price >= 8%` (configurable)
- **Rationale**: Below 8%, transaction costs and model uncertainty eat the edge.
- A 5% edge on a 50c market is NOT the same as 5% on a 90c market. Always think in terms of Kelly.

### 2.2 "Free Money" Detection / Detección de "Dinero Gratis"
- **Rule**: BUY NO tokens priced at ≤ 4% (probability) IF market has $80k+ liquidity
- **Rationale**: Markets sometimes misprice extreme outcomes. A NO at $0.96 means someone is offering you $0.04 for something that's almost certainly going to pay $1.
- **WARNING**: Free money is NEVER truly free. Always verify the market isn't about to resolve.

### 2.3 Sure Bets / Arbitrage
- **Rule**: If sum of all outcome prices < $1.00 (after fees), it's risk-free profit.
- **Threshold**: Minimum 1% profit after estimated slippage.
- **Execution**: Must buy ALL outcomes simultaneously to lock in profit.

---

## 3. Position Sizing / Dimensionamiento de Posiciones

### 3.1 Fractional Kelly Criterion
- **Formula**: `f* = α × (p × b - q) / b`
  - `p` = model probability
  - `q` = 1 - p
  - `b` = net odds = (1 - market_price) / market_price
  - `α` = 0.25 (quarter Kelly, configurable)
- **Max bet**: Never more than 5% of bankroll per position
- **Why fractional**: Full Kelly is mathematically optimal but assumes perfect probability estimates. We're not perfect. Quarter Kelly reduces drawdowns by ~75% while keeping ~50% of the growth rate.

### 3.2 Hard Limits
| Parameter                  | Default | Configurable |
|---------------------------|---------|:------------:|
| Max single position       | $100    | ✅           |
| Max open positions        | 5       | ✅           |
| Max % bankroll per bet    | 5%      | ✅           |
| Kelly alpha               | 0.25    | ✅           |

---

## 4. Market Filters / Filtros de Mercado

Every market must pass ALL filters before being considered:

| Filter                    | Threshold       | Why                                      |
|--------------------------|-----------------|------------------------------------------|
| Liquidity                | ≥ $80,000       | Thin markets = bad fills                 |
| 24h Volume               | ≥ $40,000       | Low volume = stale prices                |
| Time to Resolution       | ≥ 48 hours      | Near-resolution markets are unpredictable|
| Market Status            | Active, not closed | Only trade live markets              |
| Spread                   | < 5%            | Wide spreads eat profits                 |

---

## 5. Risk Management / Gestión de Riesgo

### 5.1 Daily Loss Limit
- **Rule**: Stop ALL trading when daily realized loss hits $50 (configurable)
- **Reset**: Next UTC day
- **No exceptions**: Even if the best opportunity of the year appears, the bot stays off.

### 5.2 Stop-Loss Per Trade
- **Rule**: Exit any position that drops 15% from entry
- **Execution**: Automatic in simulator; manual review in live
- **No averaging down**: A losing position is closed, not doubled.

### 5.3 Value at Risk (VaR)
- **Confidence**: 95% (configurable)
- **Horizon**: 24 hours
- **Model**: Parametric with assumed 20% daily vol per position
- **Rule**: Total portfolio VaR must not exceed daily loss limit

### 5.4 Liquidity Guard
- **Max order**: 2% of total market liquidity
- **Slippage limit**: 100 bps (1%)
- **Auto-resize**: If order is too large, reduce to safe size

---

## 6. Execution Rules / Reglas de Ejecución

### 6.1 Order Types
- **Default**: Limit orders (GTC) for better fills
- **Market orders**: Only for time-sensitive arbitrage (FOK)
- **Never**: Market orders on thin books

### 6.2 Timing
- Scan every 60 seconds (configurable)
- Max 2-3 new trades per scan cycle
- Don't chase: if the price moves away, let it go

### 6.3 Modes
1. **Read-only**: Scan → analyze → display. Zero risk.
2. **Simulator**: Paper trading with full statistics. Test here first.
3. **Live**: Real money. Requires `--confirm` flag. Double safety countdown.

---

## 7. What This Bot Does NOT Do

- ❌ Predict outcomes using AI/ML (plug your own model via `custom_rules.py`)
- ❌ Front-run other traders
- ❌ Manipulate markets
- ❌ Trade without explicit user authorization
- ❌ Store private keys anywhere except environment variables
- ❌ Guarantee profits (nothing does)

---

## 8. Custom Rules / Reglas Personalizadas

Edit `strategies/custom_rules.py` to add:
- Your own probability models
- Category-specific adjustments
- External data feeds integration
- Sentiment analysis signals
- Cross-market correlation detection

---

## 9. Security Checklist / Lista de Seguridad

- [ ] Private key ONLY in `.env` (never committed)
- [ ] `.env` in `.gitignore`
- [ ] Test with simulator before live
- [ ] Set conservative daily loss limits
- [ ] Enable Telegram notifications for live mode
- [ ] Review all custom rules before enabling
- [ ] Keep Kelly alpha ≤ 0.25 until confident

---

*Remember: The goal is consistent small gains over time, not one big win. Patience is the ultimate edge.*
*Recuerda: El objetivo son ganancias pequeñas y consistentes, no un gran golpe. La paciencia es la ventaja definitiva.*
