"""
strategies/custom_rules.py — Custom trading rules and model overrides
Reglas de trading personalizadas y sobrecargas del modelo

THIS IS YOUR PLAYGROUND / ESTE ES TU PLAYGROUND:
Add your own mathematical models, signals, and filters here.
Agrega aquí tus propios modelos matemáticos, señales y filtros.

Examples / Ejemplos:
- Custom probability models based on external data
- Category-specific adjustments (politics, sports, crypto)
- Time-decay signals (markets near expiration behave differently)
- Sentiment analysis integration
- Cross-market correlation signals
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from utils.helpers import MarketInfo, Opportunity


class CustomRules:
    """Custom trading rules engine / Motor de reglas de trading personalizadas.

    Override or extend the default edge detection with your own signals.
    Sobreescribe o extiende la detección de edge por defecto con tus señales.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.enabled_rules: list[str] = config.get("custom_rules", {}).get("enabled", [])

    # ------------------------------------------------------------------
    # Model probability overrides / Sobrecargas de probabilidad
    # ------------------------------------------------------------------

    def get_model_probs(self, markets: list[MarketInfo]) -> dict[str, float]:
        """Return custom model probabilities for specific tokens.
        Retornar probabilidades custom del modelo para tokens específicos.

        Override this method with your own model.
        Sobreescribe este método con tu propio modelo.

        Returns:
            dict mapping token_id -> model probability
        """
        probs: dict[str, float] = {}

        # Example: category-based adjustment
        # Ejemplo: ajuste basado en categoría
        # for market in markets:
        #     if "crypto" in market.category.lower():
        #         for token in market.tokens:
        #             # Crypto markets tend to be more volatile
        #             probs[token.token_id] = token.price * 0.95  # Slight discount
        #
        #     if "politics" in market.category.lower():
        #         for token in market.tokens:
        #             # Political markets often have informed money
        #             probs[token.token_id] = token.price  # Trust market price more

        return probs

    # ------------------------------------------------------------------
    # Post-filters / Post-filtros
    # ------------------------------------------------------------------

    def filter_opportunities(self, opportunities: list[Opportunity]) -> list[Opportunity]:
        """Apply custom post-filters to detected opportunities.
        Aplicar post-filtros custom a las oportunidades detectadas.

        Add your own filtering logic here.
        Agrega tu propia lógica de filtrado aquí.
        """
        filtered = []

        for opp in opportunities:
            # --- Rule: Skip extremely low liquidity per outcome ---
            # This catches cases where total market liquidity is high
            # but individual outcome liquidity is thin.
            # if opp.market.liquidity / max(len(opp.market.tokens), 1) < 10000:
            #     logger.debug(f"CustomRule: Skipping {opp.outcome} — thin per-outcome liquidity")
            #     continue

            # --- Rule: Boost confidence for recurring market patterns ---
            # if "election" in opp.market.question.lower():
            #     if opp.edge > 0.15:
            #         opp = opp.model_copy(update={"reason": opp.reason + " [HIGH-CONF ELECTION]"})

            # --- Rule: Skip markets with suspicious volume spikes ---
            # if opp.market.volume_24h > opp.market.volume * 0.5:
            #     logger.debug(f"CustomRule: Suspicious volume spike on {opp.outcome}")
            #     continue

            filtered.append(opp)

        if len(filtered) < len(opportunities):
            logger.info(f"CustomRules: Filtered {len(opportunities)} → {len(filtered)} opportunities")

        return filtered

    # ------------------------------------------------------------------
    # Custom scoring / Puntuación custom
    # ------------------------------------------------------------------

    def score_opportunity(self, opp: Opportunity) -> float:
        """Score an opportunity for ranking / Puntuar una oportunidad para ranking.

        Higher score = more attractive trade.
        Mayor puntaje = trade más atractivo.

        Default: edge * kelly * liquidity_factor.
        """
        liquidity_factor = min(opp.market.liquidity / 100000, 2.0)
        volume_factor = min(opp.market.volume_24h / 50000, 2.0)

        score = opp.edge * (1 + opp.kelly_fraction) * liquidity_factor * volume_factor
        return round(score, 6)

    def rank_opportunities(self, opportunities: list[Opportunity]) -> list[Opportunity]:
        """Rank opportunities by score / Rankear oportunidades por puntaje."""
        return sorted(opportunities, key=lambda o: self.score_opportunity(o), reverse=True)
