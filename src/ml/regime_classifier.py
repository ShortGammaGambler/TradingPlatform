"""
MARKET REGIME CLASSIFIER
Multi-Factor Regime Detection
Built for: Travis @ Trav's Trader Lounge

Classifies market into regimes for strategy selection:
- Volatility regime (VIX levels)
- Trend regime (momentum indicators)
- Gamma regime (dealer positioning)
- Liquidity regime (spreads, depth)

Regime determines:
- Which strategies to use
- Position sizing adjustments
- Risk parameters
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VolatilityRegime(Enum):
    """Volatility regime classification"""
    VERY_LOW = "very_low"       # VIX < 12
    LOW = "low"                  # VIX 12-15
    NORMAL = "normal"            # VIX 15-20
    ELEVATED = "elevated"        # VIX 20-25
    HIGH = "high"                # VIX 25-35
    EXTREME = "extreme"          # VIX > 35


class TrendRegime(Enum):
    """Trend regime classification"""
    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    RANGE_BOUND = "range_bound"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"
    CHOPPY = "choppy"


class GammaRegime(Enum):
    """Gamma/dealer positioning regime"""
    DEEP_POSITIVE = "deep_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    DEEP_NEGATIVE = "deep_negative"


@dataclass
class MarketRegime:
    """Complete market regime classification"""
    timestamp: datetime

    # Individual regimes
    volatility: VolatilityRegime
    trend: TrendRegime
    gamma: GammaRegime

    # Inputs used
    vix: float
    vix_percentile: float
    trend_score: float          # -100 to +100
    gamma_exposure: float       # In billions

    # Derived
    risk_level: str             # LOW, MEDIUM, HIGH, EXTREME
    strategy_bias: str          # RISK_ON, NEUTRAL, RISK_OFF
    size_multiplier: float      # 0.25 to 1.0

    # Confidence
    confidence: float           # 0-100


@dataclass
class RegimeSignal:
    """Signal from regime classification"""
    timestamp: datetime
    regime_type: str
    current: str
    previous: Optional[str]
    changed: bool
    implications: List[str]


class RegimeClassifier:
    """
    Multi-factor market regime classifier.

    Uses:
    - VIX and VIX term structure for volatility
    - Moving average relationships for trend
    - Gamma exposure data for dealer positioning
    - Breadth indicators for confirmation
    """

    # VIX thresholds
    VIX_THRESHOLDS = {
        VolatilityRegime.VERY_LOW: 12,
        VolatilityRegime.LOW: 15,
        VolatilityRegime.NORMAL: 20,
        VolatilityRegime.ELEVATED: 25,
        VolatilityRegime.HIGH: 35
    }

    # Gamma thresholds (billions)
    GAMMA_THRESHOLDS = {
        GammaRegime.DEEP_POSITIVE: 5.0,
        GammaRegime.POSITIVE: 1.0,
        GammaRegime.NEUTRAL: -1.0,
        GammaRegime.NEGATIVE: -5.0
    }

    def __init__(self):
        self._history: List[MarketRegime] = []
        self._current_regime: Optional[MarketRegime] = None

        logger.info("Regime Classifier initialized")

    def classify_volatility(self, vix: float) -> VolatilityRegime:
        """Classify volatility regime from VIX"""
        if vix < self.VIX_THRESHOLDS[VolatilityRegime.VERY_LOW]:
            return VolatilityRegime.VERY_LOW
        elif vix < self.VIX_THRESHOLDS[VolatilityRegime.LOW]:
            return VolatilityRegime.LOW
        elif vix < self.VIX_THRESHOLDS[VolatilityRegime.NORMAL]:
            return VolatilityRegime.NORMAL
        elif vix < self.VIX_THRESHOLDS[VolatilityRegime.ELEVATED]:
            return VolatilityRegime.ELEVATED
        elif vix < self.VIX_THRESHOLDS[VolatilityRegime.HIGH]:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.EXTREME

    def classify_trend(
        self,
        price: float,
        sma_20: float,
        sma_50: float,
        sma_200: float,
        atr_pct: float = 1.0
    ) -> Tuple[TrendRegime, float]:
        """
        Classify trend regime from price/MA relationships.

        Returns regime and trend score (-100 to +100)
        """
        score = 0

        # Price vs SMAs
        if price > sma_20:
            score += 25
        else:
            score -= 25

        if price > sma_50:
            score += 25
        else:
            score -= 25

        if price > sma_200:
            score += 25
        else:
            score -= 25

        # SMA alignment
        if sma_20 > sma_50 > sma_200:
            score += 25
        elif sma_20 < sma_50 < sma_200:
            score -= 25

        # Classify
        if score >= 75:
            regime = TrendRegime.STRONG_UPTREND
        elif score >= 25:
            regime = TrendRegime.UPTREND
        elif score >= -25:
            # Check for chop vs range
            if atr_pct > 2.0:
                regime = TrendRegime.CHOPPY
            else:
                regime = TrendRegime.RANGE_BOUND
        elif score >= -75:
            regime = TrendRegime.DOWNTREND
        else:
            regime = TrendRegime.STRONG_DOWNTREND

        return regime, score

    def classify_gamma(self, gamma_exposure: float) -> GammaRegime:
        """Classify gamma regime from dealer positioning"""
        if gamma_exposure > self.GAMMA_THRESHOLDS[GammaRegime.DEEP_POSITIVE]:
            return GammaRegime.DEEP_POSITIVE
        elif gamma_exposure > self.GAMMA_THRESHOLDS[GammaRegime.POSITIVE]:
            return GammaRegime.POSITIVE
        elif gamma_exposure > self.GAMMA_THRESHOLDS[GammaRegime.NEUTRAL]:
            return GammaRegime.NEUTRAL
        elif gamma_exposure > self.GAMMA_THRESHOLDS[GammaRegime.NEGATIVE]:
            return GammaRegime.NEGATIVE
        else:
            return GammaRegime.DEEP_NEGATIVE

    def classify(
        self,
        vix: float,
        price: float,
        sma_20: float,
        sma_50: float,
        sma_200: float,
        gamma_exposure: float = 0.0,
        atr_pct: float = 1.0,
        vix_percentile: float = 50.0
    ) -> MarketRegime:
        """
        Perform full regime classification.

        Args:
            vix: Current VIX level
            price: Current price (SPY/SPX)
            sma_20/50/200: Moving averages
            gamma_exposure: Net gamma in billions
            atr_pct: ATR as % of price
            vix_percentile: VIX percentile rank

        Returns:
            Complete MarketRegime classification
        """
        # Classify each dimension
        vol_regime = self.classify_volatility(vix)
        trend_regime, trend_score = self.classify_trend(price, sma_20, sma_50, sma_200, atr_pct)
        gamma_regime = self.classify_gamma(gamma_exposure)

        # Determine risk level
        risk_scores = {
            VolatilityRegime.VERY_LOW: 1,
            VolatilityRegime.LOW: 2,
            VolatilityRegime.NORMAL: 3,
            VolatilityRegime.ELEVATED: 4,
            VolatilityRegime.HIGH: 5,
            VolatilityRegime.EXTREME: 6
        }

        gamma_risk = {
            GammaRegime.DEEP_POSITIVE: 1,
            GammaRegime.POSITIVE: 2,
            GammaRegime.NEUTRAL: 3,
            GammaRegime.NEGATIVE: 4,
            GammaRegime.DEEP_NEGATIVE: 5
        }

        risk_score = (risk_scores[vol_regime] + gamma_risk[gamma_regime]) / 2

        if risk_score <= 2:
            risk_level = "LOW"
        elif risk_score <= 3:
            risk_level = "MEDIUM"
        elif risk_score <= 4:
            risk_level = "HIGH"
        else:
            risk_level = "EXTREME"

        # Determine strategy bias
        if trend_score > 25 and gamma_regime in [GammaRegime.POSITIVE, GammaRegime.DEEP_POSITIVE]:
            strategy_bias = "RISK_ON"
        elif trend_score < -25 or vol_regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]:
            strategy_bias = "RISK_OFF"
        else:
            strategy_bias = "NEUTRAL"

        # Calculate size multiplier
        size_map = {
            "LOW": 1.0,
            "MEDIUM": 0.75,
            "HIGH": 0.5,
            "EXTREME": 0.25
        }
        size_multiplier = size_map[risk_level]

        # Confidence based on alignment
        alignment_score = 0

        # Vol and gamma aligned?
        if (vol_regime in [VolatilityRegime.LOW, VolatilityRegime.NORMAL] and
            gamma_regime in [GammaRegime.POSITIVE, GammaRegime.DEEP_POSITIVE]):
            alignment_score += 30
        elif (vol_regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME] and
              gamma_regime in [GammaRegime.NEGATIVE, GammaRegime.DEEP_NEGATIVE]):
            alignment_score += 30

        # Trend clear?
        if abs(trend_score) > 50:
            alignment_score += 30

        # VIX percentile confirms level?
        if (vix_percentile > 70 and vol_regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]) or \
           (vix_percentile < 30 and vol_regime in [VolatilityRegime.LOW, VolatilityRegime.VERY_LOW]):
            alignment_score += 20

        confidence = min(95, 50 + alignment_score)

        regime = MarketRegime(
            timestamp=datetime.now(),
            volatility=vol_regime,
            trend=trend_regime,
            gamma=gamma_regime,
            vix=vix,
            vix_percentile=vix_percentile,
            trend_score=trend_score,
            gamma_exposure=gamma_exposure,
            risk_level=risk_level,
            strategy_bias=strategy_bias,
            size_multiplier=size_multiplier,
            confidence=confidence
        )

        # Check for regime change
        if self._current_regime:
            self._check_regime_change(self._current_regime, regime)

        self._current_regime = regime
        self._history.append(regime)

        return regime

    def _check_regime_change(
        self,
        previous: MarketRegime,
        current: MarketRegime
    ) -> List[RegimeSignal]:
        """Check for and log regime changes"""
        signals = []

        if previous.volatility != current.volatility:
            signals.append(RegimeSignal(
                timestamp=datetime.now(),
                regime_type="volatility",
                current=current.volatility.value,
                previous=previous.volatility.value,
                changed=True,
                implications=self._get_vol_implications(current.volatility)
            ))

        if previous.gamma != current.gamma:
            signals.append(RegimeSignal(
                timestamp=datetime.now(),
                regime_type="gamma",
                current=current.gamma.value,
                previous=previous.gamma.value,
                changed=True,
                implications=self._get_gamma_implications(current.gamma)
            ))

        for signal in signals:
            logger.info(f"Regime change: {signal.regime_type} {signal.previous} -> {signal.current}")

        return signals

    def _get_vol_implications(self, regime: VolatilityRegime) -> List[str]:
        """Get strategy implications for volatility regime"""
        implications = {
            VolatilityRegime.VERY_LOW: [
                "Buy premium is cheap",
                "Consider long straddles/strangles",
                "VIX calls as hedge"
            ],
            VolatilityRegime.LOW: [
                "Premium slightly cheap",
                "Watch for volatility expansion",
                "Standard strategies work"
            ],
            VolatilityRegime.NORMAL: [
                "Fair value premium",
                "All strategies viable",
                "Normal position sizing"
            ],
            VolatilityRegime.ELEVATED: [
                "Premium getting expensive",
                "Consider selling premium",
                "Reduce position sizes"
            ],
            VolatilityRegime.HIGH: [
                "Sell premium opportunities",
                "Wide iron condors",
                "Significantly reduce size"
            ],
            VolatilityRegime.EXTREME: [
                "Crisis mode - mostly cash",
                "Only sell expensive premium",
                "Minimal position sizes"
            ]
        }
        return implications.get(regime, [])

    def _get_gamma_implications(self, regime: GammaRegime) -> List[str]:
        """Get strategy implications for gamma regime"""
        implications = {
            GammaRegime.DEEP_POSITIVE: [
                "Strong mean reversion expected",
                "Fade moves, sell premium",
                "Iron condors favored"
            ],
            GammaRegime.POSITIVE: [
                "Mild mean reversion",
                "Range-bound strategies work",
                "Standard approach"
            ],
            GammaRegime.NEUTRAL: [
                "No clear gamma edge",
                "Follow technicals",
                "Watch for shift"
            ],
            GammaRegime.NEGATIVE: [
                "Momentum amplified",
                "Follow trends, don't fade",
                "Reduce size"
            ],
            GammaRegime.DEEP_NEGATIVE: [
                "DANGER - dealers amplify moves",
                "Strong momentum expected",
                "Minimal size, buy protection"
            ]
        }
        return implications.get(regime, [])

    def get_strategy_recommendations(self, regime: MarketRegime) -> Dict:
        """Get specific strategy recommendations for current regime"""
        recommendations = {
            "primary_strategies": [],
            "avoid": [],
            "adjustments": []
        }

        # Volatility-based
        if regime.volatility in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]:
            recommendations["primary_strategies"].extend([
                "Iron condors (wide wings)",
                "Credit spreads",
                "Short strangles (if experienced)"
            ])
            recommendations["avoid"].append("Naked long options")
        elif regime.volatility in [VolatilityRegime.VERY_LOW, VolatilityRegime.LOW]:
            recommendations["primary_strategies"].extend([
                "Long straddles",
                "Calendar spreads",
                "Directional plays with defined risk"
            ])
            recommendations["avoid"].append("Selling naked premium")

        # Gamma-based
        if regime.gamma in [GammaRegime.POSITIVE, GammaRegime.DEEP_POSITIVE]:
            recommendations["primary_strategies"].append("Mean reversion plays")
            recommendations["adjustments"].append("Fade extreme moves")
        elif regime.gamma in [GammaRegime.NEGATIVE, GammaRegime.DEEP_NEGATIVE]:
            recommendations["primary_strategies"].append("Momentum/trend following")
            recommendations["adjustments"].append("Don't fight the trend")
            recommendations["avoid"].append("Fading moves")

        # Trend-based
        if regime.trend in [TrendRegime.STRONG_UPTREND, TrendRegime.UPTREND]:
            recommendations["primary_strategies"].append("Bull call spreads")
            recommendations["adjustments"].append("Bullish bias")
        elif regime.trend in [TrendRegime.STRONG_DOWNTREND, TrendRegime.DOWNTREND]:
            recommendations["primary_strategies"].append("Bear put spreads")
            recommendations["adjustments"].append("Bearish bias, hedges important")

        # Size adjustment
        recommendations["size_multiplier"] = regime.size_multiplier
        recommendations["risk_level"] = regime.risk_level

        return recommendations

    def generate_report(self, regime: MarketRegime) -> str:
        """Generate formatted regime report"""
        lines = []
        lines.append("=" * 60)
        lines.append("MARKET REGIME CLASSIFICATION")
        lines.append("=" * 60)
        lines.append(f"Timestamp: {regime.timestamp.strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        lines.append("CURRENT REGIMES:")
        lines.append("-" * 40)
        lines.append(f"  Volatility:  {regime.volatility.value.upper():20} (VIX: {regime.vix:.1f})")
        lines.append(f"  Trend:       {regime.trend.value.upper():20} (Score: {regime.trend_score:+.0f})")
        lines.append(f"  Gamma:       {regime.gamma.value.upper():20} (GEX: {regime.gamma_exposure:+.1f}B)")
        lines.append("")

        lines.append("ASSESSMENT:")
        lines.append("-" * 40)
        lines.append(f"  Risk Level:      {regime.risk_level}")
        lines.append(f"  Strategy Bias:   {regime.strategy_bias}")
        lines.append(f"  Size Multiplier: {regime.size_multiplier:.0%}")
        lines.append(f"  Confidence:      {regime.confidence:.0f}%")
        lines.append("")

        recs = self.get_strategy_recommendations(regime)

        lines.append("RECOMMENDATIONS:")
        lines.append("-" * 40)
        lines.append("  Primary Strategies:")
        for strat in recs["primary_strategies"][:3]:
            lines.append(f"    + {strat}")

        if recs["avoid"]:
            lines.append("  Avoid:")
            for avoid in recs["avoid"][:2]:
                lines.append(f"    - {avoid}")

        if recs["adjustments"]:
            lines.append("  Adjustments:")
            for adj in recs["adjustments"][:2]:
                lines.append(f"    * {adj}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("REGIME CLASSIFIER")
    print("=" * 60)

    classifier = RegimeClassifier()

    # Classify current regime
    regime = classifier.classify(
        vix=18.5,
        price=510,
        sma_20=508,
        sma_50=505,
        sma_200=490,
        gamma_exposure=2.5,
        atr_pct=1.2,
        vix_percentile=45
    )

    print(classifier.generate_report(regime))
