"""
DEALER POSITIONING MODULE
Gamma Exposure and COT Analysis
Built for: Travis @ Trav's Trader Lounge

This module tracks:
1. Gamma Exposure (GEX) - Dealer hedging flows
2. COT Positioning - CFTC Commitment of Traders data
3. Key Options Levels - Walls, flips, max pain

Understanding dealer positioning tells you WHO has to buy/sell.
"""

import requests
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GammaEnvironment(Enum):
    """Market gamma environment classification"""
    DEEP_POSITIVE = "deep_positive"      # > +5B GEX, strong mean reversion
    POSITIVE = "positive"                 # +1B to +5B, mild mean reversion
    NEUTRAL = "neutral"                   # -1B to +1B
    NEGATIVE = "negative"                 # -5B to -1B, momentum amplified
    DEEP_NEGATIVE = "deep_negative"       # < -5B, high volatility


@dataclass
class GammaExposure:
    """Gamma exposure data for an underlying"""
    symbol: str
    timestamp: datetime
    total_gex: float              # Total gamma exposure in $ billions
    call_gex: float               # Call gamma exposure
    put_gex: float                # Put gamma exposure
    gamma_flip: float             # Price where gamma flips sign
    call_wall: float              # Largest call OI strike
    put_wall: float               # Largest put OI strike
    max_pain: float               # Max pain strike
    expected_move_1d: float       # 1-day expected move
    expected_move_1w: float       # 1-week expected move
    environment: GammaEnvironment = GammaEnvironment.NEUTRAL

    @property
    def net_gex(self) -> float:
        return self.call_gex + self.put_gex


@dataclass
class KeyLevel:
    """Key options level (wall, flip, support/resistance)"""
    strike: float
    level_type: str               # 'call_wall', 'put_wall', 'gamma_flip', 'high_oi'
    gamma_at_strike: float        # Gamma exposure at this strike
    open_interest: int            # Total OI at strike
    significance_score: float     # 0-100, how important this level is
    description: str


@dataclass
class COTPositions:
    """CFTC Commitment of Traders positions"""
    symbol: str
    report_date: date

    # Commercial (hedgers)
    commercial_long: int = 0
    commercial_short: int = 0
    commercial_net: int = 0

    # Non-commercial (speculators/funds)
    noncommercial_long: int = 0
    noncommercial_short: int = 0
    noncommercial_net: int = 0

    # Non-reportable (retail)
    nonreportable_long: int = 0
    nonreportable_short: int = 0
    nonreportable_net: int = 0

    # Open interest
    total_oi: int = 0
    change_in_oi: int = 0

    # Percentile ranks (historical context)
    commercial_net_percentile: float = 50.0
    noncommercial_net_percentile: float = 50.0


class GammaExposureTracker:
    """
    Track and analyze gamma exposure.

    Data sources:
    - SpotGamma API (premium, most accurate)
    - Estimated from options chain (free, less accurate)
    - CBOE data (delayed)

    In positive gamma, dealers are long gamma and will:
    - Buy dips (hedge puts by buying stock)
    - Sell rips (hedge calls by selling stock)
    - Result: Mean reversion, compressed moves

    In negative gamma, dealers are short gamma and will:
    - Sell dips (hedge puts by selling stock)
    - Buy rips (hedge calls by buying stock)
    - Result: Momentum amplification, larger moves
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._cache: Dict[str, GammaExposure] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = 300  # 5 minutes

        logger.info("Gamma Exposure Tracker initialized")

    def get_current_gex(self, symbol: str = "SPX") -> GammaExposure:
        """
        Get current gamma exposure for symbol.

        Falls back to estimated data if no API key.
        """
        # Check cache
        if symbol in self._cache:
            cache_age = (datetime.now() - self._cache_time.get(symbol, datetime.min)).seconds
            if cache_age < self._cache_ttl:
                return self._cache[symbol]

        if self.api_key:
            gex = self._fetch_spotgamma_gex(symbol)
        else:
            gex = self._estimate_gex(symbol)

        # Cache result
        self._cache[symbol] = gex
        self._cache_time[symbol] = datetime.now()

        return gex

    def _fetch_spotgamma_gex(self, symbol: str) -> GammaExposure:
        """Fetch from SpotGamma API (requires subscription)"""
        # This would call the actual SpotGamma API
        # For now, return estimated data
        logger.info(f"Would fetch SpotGamma data for {symbol}")
        return self._estimate_gex(symbol)

    def _estimate_gex(self, symbol: str) -> GammaExposure:
        """
        Estimate gamma exposure from available data.

        This is a simplified model. Real GEX calculation requires:
        - Full options chain with OI
        - Dealer/customer positioning split
        - Greek calculations for each strike
        """
        # Mock data based on typical SPX levels
        # In production, calculate from options chain

        import random

        # Simulate different gamma environments
        base_gex = random.uniform(-3, 5)  # Billions

        if base_gex > 3:
            env = GammaEnvironment.DEEP_POSITIVE
        elif base_gex > 0.5:
            env = GammaEnvironment.POSITIVE
        elif base_gex > -0.5:
            env = GammaEnvironment.NEUTRAL
        elif base_gex > -3:
            env = GammaEnvironment.NEGATIVE
        else:
            env = GammaEnvironment.DEEP_NEGATIVE

        # Typical SPX levels (would be calculated from chain)
        current_price = 5100  # Would fetch real price

        return GammaExposure(
            symbol=symbol,
            timestamp=datetime.now(),
            total_gex=base_gex,
            call_gex=base_gex * 0.7 if base_gex > 0 else base_gex * 0.3,
            put_gex=base_gex * 0.3 if base_gex > 0 else base_gex * 0.7,
            gamma_flip=current_price - 25,  # Typically slightly below spot
            call_wall=current_price + 75,   # Major call OI
            put_wall=current_price - 100,   # Major put OI
            max_pain=current_price - 10,
            expected_move_1d=current_price * 0.008,  # ~0.8% daily
            expected_move_1w=current_price * 0.02,   # ~2% weekly
            environment=env
        )

    def get_key_levels(self, symbol: str = "SPX") -> List[KeyLevel]:
        """Get key options levels for trading"""
        gex = self.get_current_gex(symbol)

        levels = [
            KeyLevel(
                strike=gex.gamma_flip,
                level_type="gamma_flip",
                gamma_at_strike=0,
                open_interest=0,
                significance_score=95,
                description="Gamma flip point - regime change level"
            ),
            KeyLevel(
                strike=gex.call_wall,
                level_type="call_wall",
                gamma_at_strike=gex.call_gex * 0.4,
                open_interest=150000,  # Mock
                significance_score=90,
                description="Major call wall - resistance, target for longs"
            ),
            KeyLevel(
                strike=gex.put_wall,
                level_type="put_wall",
                gamma_at_strike=gex.put_gex * 0.4,
                open_interest=120000,  # Mock
                significance_score=85,
                description="Major put wall - support, target for shorts"
            ),
            KeyLevel(
                strike=gex.max_pain,
                level_type="max_pain",
                gamma_at_strike=0,
                open_interest=0,
                significance_score=70,
                description="Max pain - price gravitates here into expiry"
            )
        ]

        return sorted(levels, key=lambda x: -x.significance_score)

    def interpret_gex(self, gex: GammaExposure) -> Dict:
        """Provide trading interpretation of gamma exposure"""
        interpretations = {
            GammaEnvironment.DEEP_POSITIVE: {
                "bias": "MEAN_REVERSION",
                "volatility": "COMPRESSED",
                "strategy": "Sell premium, fade extremes, iron condors",
                "warning": "Breakouts unlikely to sustain",
                "size_adjustment": 1.0
            },
            GammaEnvironment.POSITIVE: {
                "bias": "MILD_MEAN_REVERSION",
                "volatility": "NORMAL",
                "strategy": "Standard strategies, slight edge to premium selling",
                "warning": None,
                "size_adjustment": 1.0
            },
            GammaEnvironment.NEUTRAL: {
                "bias": "NEUTRAL",
                "volatility": "NORMAL",
                "strategy": "Follow technicals, no gamma edge",
                "warning": "Watch for gamma flip",
                "size_adjustment": 1.0
            },
            GammaEnvironment.NEGATIVE: {
                "bias": "MOMENTUM",
                "volatility": "ELEVATED",
                "strategy": "Trend following, buy premium for protection",
                "warning": "Moves will be amplified",
                "size_adjustment": 0.75
            },
            GammaEnvironment.DEEP_NEGATIVE: {
                "bias": "STRONG_MOMENTUM",
                "volatility": "HIGH",
                "strategy": "Reduce size, buy protection, follow momentum",
                "warning": "DANGER - dealers will amplify all moves",
                "size_adjustment": 0.5
            }
        }

        interp = interpretations.get(gex.environment, interpretations[GammaEnvironment.NEUTRAL])

        return {
            "environment": gex.environment.value,
            "total_gex": f"${gex.total_gex:.2f}B",
            "key_levels": {
                "gamma_flip": gex.gamma_flip,
                "call_wall": gex.call_wall,
                "put_wall": gex.put_wall
            },
            "expected_range": {
                "daily": f"+/- ${gex.expected_move_1d:.0f}",
                "weekly": f"+/- ${gex.expected_move_1w:.0f}"
            },
            **interp
        }


class COTAnalyzer:
    """
    Analyze CFTC Commitment of Traders data.

    COT shows futures positioning by:
    - Commercials (hedgers) - Usually fade them, they hedge business
    - Non-Commercials (specs/funds) - Smart money, but crowded = reversal
    - Non-Reportables (retail) - Contrarian indicator

    Key insight: Extreme positioning = reversal risk
    """

    COT_BASE_URL = "https://publicreporting.cftc.gov/api/id/"

    # CFTC codes for common contracts
    CFTC_CODES = {
        "ES": "13874A",     # E-mini S&P 500
        "NQ": "209742",     # E-mini NASDAQ
        "RTY": "239742",    # E-mini Russell
        "YM": "124606",     # E-mini Dow
        "CL": "067651",     # Crude Oil
        "GC": "088691",     # Gold
        "SI": "084691",     # Silver
        "ZN": "043602",     # 10-Year Note
        "ZB": "020601",     # 30-Year Bond
        "6E": "099741",     # Euro FX
    }

    def __init__(self):
        self._cache: Dict[str, COTPositions] = {}
        self._historical: Dict[str, List[COTPositions]] = {}

        logger.info("COT Analyzer initialized")

    def get_cot_data(self, symbol: str = "ES") -> COTPositions:
        """
        Get latest COT data for symbol.

        Note: COT is released Tuesday, covering positions as of prior Tuesday.
        Data is inherently lagged by ~3-4 days.
        """
        if symbol in self._cache:
            return self._cache[symbol]

        # In production, fetch from CFTC API
        # For now, return mock data
        positions = self._mock_cot_data(symbol)
        self._cache[symbol] = positions

        return positions

    def _mock_cot_data(self, symbol: str) -> COTPositions:
        """Generate mock COT data for testing"""
        import random

        # Simulate typical positioning
        comm_bias = random.uniform(-0.3, 0.3)
        spec_bias = random.uniform(-0.4, 0.4)

        total_oi = 2500000 + random.randint(-500000, 500000)

        comm_long = int(total_oi * 0.35 * (1 + comm_bias))
        comm_short = int(total_oi * 0.35 * (1 - comm_bias))

        noncomm_long = int(total_oi * 0.45 * (1 + spec_bias))
        noncomm_short = int(total_oi * 0.45 * (1 - spec_bias))

        nonrep_long = int(total_oi * 0.10)
        nonrep_short = int(total_oi * 0.10)

        return COTPositions(
            symbol=symbol,
            report_date=date.today() - timedelta(days=date.today().weekday() + 2),  # Last Tuesday
            commercial_long=comm_long,
            commercial_short=comm_short,
            commercial_net=comm_long - comm_short,
            noncommercial_long=noncomm_long,
            noncommercial_short=noncomm_short,
            noncommercial_net=noncomm_long - noncomm_short,
            nonreportable_long=nonrep_long,
            nonreportable_short=nonrep_short,
            nonreportable_net=nonrep_long - nonrep_short,
            total_oi=total_oi,
            change_in_oi=random.randint(-50000, 50000),
            commercial_net_percentile=random.uniform(20, 80),
            noncommercial_net_percentile=random.uniform(20, 80)
        )

    def calculate_sentiment(self, positions: COTPositions) -> Dict:
        """Calculate sentiment indicators from COT"""
        # Net positioning as % of total OI
        if positions.total_oi == 0:
            return {"error": "No open interest data"}

        commercial_pct = positions.commercial_net / positions.total_oi * 100
        noncommercial_pct = positions.noncommercial_net / positions.total_oi * 100

        # Extremes
        extreme_bullish_spec = positions.noncommercial_net_percentile > 80
        extreme_bearish_spec = positions.noncommercial_net_percentile < 20

        # Divergence (commercials vs speculators)
        divergence = (positions.commercial_net > 0 and positions.noncommercial_net < 0) or \
                     (positions.commercial_net < 0 and positions.noncommercial_net > 0)

        sentiment = {
            "report_date": positions.report_date.isoformat(),
            "commercial_net_pct": commercial_pct,
            "noncommercial_net_pct": noncommercial_pct,
            "commercial_net_percentile": positions.commercial_net_percentile,
            "noncommercial_net_percentile": positions.noncommercial_net_percentile,
            "extreme_bullish_spec": extreme_bullish_spec,
            "extreme_bearish_spec": extreme_bearish_spec,
            "divergence": divergence,
            "extreme_reading": extreme_bullish_spec or extreme_bearish_spec
        }

        # Interpretation
        if extreme_bullish_spec:
            sentiment["interpretation"] = "Specs extremely long - crowded trade, reversal risk"
            sentiment["divergence_interpretation"] = "BEARISH - fade speculator crowding"
        elif extreme_bearish_spec:
            sentiment["interpretation"] = "Specs extremely short - potential short squeeze"
            sentiment["divergence_interpretation"] = "BULLISH - specs offsides"
        elif divergence:
            if positions.commercial_net > 0:
                sentiment["interpretation"] = "Commercials accumulating, specs selling"
                sentiment["divergence_interpretation"] = "BULLISH - follow smart hedgers"
            else:
                sentiment["interpretation"] = "Commercials reducing, specs buying"
                sentiment["divergence_interpretation"] = "BEARISH - commercials distributing"
        else:
            sentiment["interpretation"] = "No extreme positioning"
            sentiment["divergence_interpretation"] = "NEUTRAL"

        return sentiment


class DealerPositioningMonitor:
    """
    Combined dealer positioning monitor.

    Integrates gamma exposure and COT for complete picture.
    """

    def __init__(
        self,
        spotgamma_api_key: Optional[str] = None
    ):
        self.gamma = GammaExposureTracker(spotgamma_api_key)
        self.cot = COTAnalyzer()

        logger.info("Dealer Positioning Monitor initialized")

    def get_full_positioning(self, symbol: str = "SPX") -> Dict:
        """Get complete positioning picture"""
        gex = self.gamma.get_current_gex(symbol)
        gex_interp = self.gamma.interpret_gex(gex)

        # Map equity symbol to futures
        futures_map = {"SPX": "ES", "SPY": "ES", "QQQ": "NQ", "IWM": "RTY"}
        futures_symbol = futures_map.get(symbol, "ES")

        cot = self.cot.get_cot_data(futures_symbol)
        cot_sentiment = self.cot.calculate_sentiment(cot)

        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "gamma": {
                "environment": gex.environment.value,
                "total_gex": gex.total_gex,
                "levels": {
                    "flip": gex.gamma_flip,
                    "call_wall": gex.call_wall,
                    "put_wall": gex.put_wall
                },
                "interpretation": gex_interp
            },
            "cot": {
                "report_date": cot.report_date.isoformat(),
                "noncommercial_net": cot.noncommercial_net,
                "noncommercial_percentile": cot.noncommercial_net_percentile,
                "sentiment": cot_sentiment
            },
            "combined_view": self._combine_signals(gex_interp, cot_sentiment)
        }

    def _combine_signals(self, gex_interp: Dict, cot_sentiment: Dict) -> Dict:
        """Combine gamma and COT into unified view"""
        gamma_bias = gex_interp.get("bias", "NEUTRAL")
        cot_bias = cot_sentiment.get("divergence_interpretation", "NEUTRAL")

        # Agreement check
        bullish_gamma = gamma_bias in ["MEAN_REVERSION", "MILD_MEAN_REVERSION"]
        bullish_cot = "BULLISH" in cot_bias

        bearish_gamma = gamma_bias in ["MOMENTUM", "STRONG_MOMENTUM"]
        bearish_cot = "BEARISH" in cot_bias

        if bullish_cot and not bearish_gamma:
            combined = "BULLISH"
            confidence = "HIGH" if bullish_gamma else "MEDIUM"
        elif bearish_cot and not bullish_gamma:
            combined = "BEARISH"
            confidence = "HIGH" if bearish_gamma else "MEDIUM"
        elif bullish_gamma and bearish_cot:
            combined = "MIXED"
            confidence = "LOW"
        elif bearish_gamma and bullish_cot:
            combined = "MIXED"
            confidence = "LOW"
        else:
            combined = "NEUTRAL"
            confidence = "LOW"

        return {
            "direction": combined,
            "confidence": confidence,
            "gamma_says": gamma_bias,
            "cot_says": cot_bias,
            "size_adjustment": gex_interp.get("size_adjustment", 1.0),
            "strategy_hint": gex_interp.get("strategy", "Standard approach"),
            "warning": gex_interp.get("warning") or cot_sentiment.get("interpretation")
        }


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("DEALER POSITIONING ANALYSIS")
    print("=" * 60)

    monitor = DealerPositioningMonitor()

    # Get full positioning
    positioning = monitor.get_full_positioning("SPX")

    print(f"\nSymbol: {positioning['symbol']}")
    print(f"Timestamp: {positioning['timestamp']}")

    print("\n=== GAMMA EXPOSURE ===")
    gamma = positioning['gamma']
    print(f"  Environment: {gamma['environment']}")
    print(f"  Total GEX: ${gamma['total_gex']:.2f}B")
    print(f"  Gamma Flip: {gamma['levels']['flip']}")
    print(f"  Call Wall: {gamma['levels']['call_wall']}")
    print(f"  Put Wall: {gamma['levels']['put_wall']}")
    print(f"  Bias: {gamma['interpretation']['bias']}")
    print(f"  Strategy: {gamma['interpretation']['strategy']}")

    print("\n=== COT POSITIONING ===")
    cot = positioning['cot']
    print(f"  Report Date: {cot['report_date']}")
    print(f"  Spec Net: {cot['noncommercial_net']:,}")
    print(f"  Spec Percentile: {cot['noncommercial_percentile']:.1f}")
    print(f"  Interpretation: {cot['sentiment']['interpretation']}")

    print("\n=== COMBINED VIEW ===")
    combined = positioning['combined_view']
    print(f"  Direction: {combined['direction']}")
    print(f"  Confidence: {combined['confidence']}")
    print(f"  Size Adjustment: {combined['size_adjustment']}")
    print(f"  Strategy: {combined['strategy_hint']}")
    if combined['warning']:
        print(f"  Warning: {combined['warning']}")
