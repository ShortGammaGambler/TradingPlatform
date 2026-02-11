"""
ALTERNATIVE DATA ENGINE
Non-Traditional Market Signals
Built for: Travis @ Trav's Trader Lounge

This module tracks:
1. Social Sentiment - Reddit, Twitter, StockTwits
2. Web Traffic - Company website trends
3. App Downloads - Consumer behavior
4. Satellite/Geospatial (future)

Alt data is about seeing what others don't.
Edge comes from speed, uniqueness, or interpretation.
"""

import requests
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SentimentSignal(Enum):
    """Sentiment signal classification"""
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


@dataclass
class SentimentData:
    """Aggregated sentiment data for a symbol"""
    symbol: str
    timestamp: datetime
    raw_score: float          # -100 to +100
    signal: SentimentSignal
    volume: int               # Number of mentions
    volume_change_pct: float  # vs prior period
    sources: Dict[str, float] = field(default_factory=dict)  # Source -> score

    @property
    def is_extreme(self) -> bool:
        return abs(self.raw_score) > 70


@dataclass
class SentimentTrend:
    """Sentiment trend over time"""
    symbol: str
    period_days: int
    start_score: float
    end_score: float
    trend_direction: str      # IMPROVING, WORSENING, STABLE
    momentum: float           # Rate of change


@dataclass
class WebTrafficData:
    """Website traffic data for a company"""
    symbol: str
    domain: str
    timestamp: datetime
    monthly_visits: int
    monthly_visits_change_pct: float
    bounce_rate: float
    avg_visit_duration: float
    pages_per_visit: float
    traffic_rank: int
    traffic_rank_change: int


class SentimentAnalyzer:
    """
    Analyze social sentiment from multiple sources.

    Sources:
    - Reddit (r/wallstreetbets, r/stocks, r/options)
    - StockTwits
    - Twitter/X
    - News sentiment

    Key insight: Extreme sentiment = contrarian opportunity
    """

    def __init__(self):
        self._cache: Dict[str, SentimentData] = {}
        self._history: Dict[str, List[SentimentData]] = {}

        logger.info("Sentiment Analyzer initialized")

    def get_social_sentiment(self, symbol: str) -> SentimentData:
        """
        Get aggregated social sentiment for symbol.

        In production, would aggregate from multiple APIs.
        """
        # Check cache (5 min TTL)
        cache_key = f"{symbol}_{datetime.now().strftime('%Y%m%d%H%M')[:11]}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Generate mock sentiment (in production, fetch from APIs)
        sentiment = self._mock_sentiment(symbol)

        # Cache
        self._cache[cache_key] = sentiment

        # Add to history
        if symbol not in self._history:
            self._history[symbol] = []
        self._history[symbol].append(sentiment)

        return sentiment

    def _mock_sentiment(self, symbol: str) -> SentimentData:
        """Generate mock sentiment data"""
        # Simulate sentiment with some randomness
        base_score = random.gauss(0, 30)
        base_score = max(-100, min(100, base_score))

        # Determine signal
        if base_score > 60:
            signal = SentimentSignal.VERY_BULLISH
        elif base_score > 20:
            signal = SentimentSignal.BULLISH
        elif base_score > -20:
            signal = SentimentSignal.NEUTRAL
        elif base_score > -60:
            signal = SentimentSignal.BEARISH
        else:
            signal = SentimentSignal.VERY_BEARISH

        return SentimentData(
            symbol=symbol,
            timestamp=datetime.now(),
            raw_score=base_score,
            signal=signal,
            volume=random.randint(100, 10000),
            volume_change_pct=random.uniform(-50, 100),
            sources={
                "reddit": base_score + random.gauss(0, 10),
                "stocktwits": base_score + random.gauss(0, 15),
                "twitter": base_score + random.gauss(0, 20),
                "news": base_score + random.gauss(0, 10)
            }
        )

    def get_sentiment_trend(
        self,
        symbol: str,
        days: int = 7
    ) -> Optional[SentimentTrend]:
        """Get sentiment trend over time"""
        history = self._history.get(symbol, [])

        if len(history) < 2:
            # Generate some history
            for i in range(days):
                self.get_social_sentiment(symbol)
            history = self._history.get(symbol, [])

        if len(history) < 2:
            return None

        # Calculate trend
        start_score = history[0].raw_score
        end_score = history[-1].raw_score
        change = end_score - start_score

        if change > 10:
            direction = "IMPROVING"
        elif change < -10:
            direction = "WORSENING"
        else:
            direction = "STABLE"

        return SentimentTrend(
            symbol=symbol,
            period_days=days,
            start_score=start_score,
            end_score=end_score,
            trend_direction=direction,
            momentum=change / days
        )

    def detect_sentiment_divergence(
        self,
        symbol: str,
        price_change_pct: float = None
    ) -> Optional[Dict]:
        """
        Detect divergence between sentiment and price.

        Divergence = potential reversal signal
        - Price up + Sentiment down = bearish divergence
        - Price down + Sentiment up = bullish divergence
        """
        sentiment = self.get_social_sentiment(symbol)
        trend = self.get_sentiment_trend(symbol)

        if not trend:
            return None

        # Mock price change if not provided
        if price_change_pct is None:
            price_change_pct = random.uniform(-5, 5)

        # Detect divergence
        sentiment_improving = trend.momentum > 0.5
        sentiment_worsening = trend.momentum < -0.5
        price_up = price_change_pct > 1
        price_down = price_change_pct < -1

        divergence = None
        if price_up and sentiment_worsening:
            divergence = {
                "type": "BEARISH",
                "description": "Price rising but sentiment deteriorating",
                "interpretation": "Smart money may be selling into strength",
                "confidence": min(80, abs(trend.momentum) * 20 + abs(price_change_pct) * 5),
                "divergence_detected": True
            }
        elif price_down and sentiment_improving:
            divergence = {
                "type": "BULLISH",
                "description": "Price falling but sentiment improving",
                "interpretation": "Accumulation during weakness",
                "confidence": min(80, abs(trend.momentum) * 20 + abs(price_change_pct) * 5),
                "divergence_detected": True
            }
        else:
            divergence = {
                "type": "NONE",
                "description": "No significant divergence",
                "divergence_detected": False
            }

        return divergence

    def get_extreme_sentiment_symbols(
        self,
        watchlist: List[str],
        threshold: float = 70
    ) -> Dict[str, List[str]]:
        """Find symbols with extreme sentiment (contrarian opportunities)"""
        very_bullish = []
        very_bearish = []

        for symbol in watchlist:
            sentiment = self.get_social_sentiment(symbol)

            if sentiment.raw_score > threshold:
                very_bullish.append(symbol)
            elif sentiment.raw_score < -threshold:
                very_bearish.append(symbol)

        return {
            "very_bullish": very_bullish,  # Contrarian sell/short candidates
            "very_bearish": very_bearish,   # Contrarian buy candidates
            "interpretation": (
                "Extreme bullish sentiment = crowded long, consider fading. "
                "Extreme bearish sentiment = crowded short, consider buying."
            )
        }


class WebTrafficAnalyzer:
    """
    Analyze web traffic as alternative data.

    Rising traffic to company sites can precede earnings beats.
    Traffic to product pages shows consumer demand.

    Sources:
    - SimilarWeb API
    - Alexa (deprecated but concepts apply)
    - SEMrush
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

        logger.info("Web Traffic Analyzer initialized")

    def get_traffic_data(self, symbol: str) -> WebTrafficData:
        """Get website traffic data for company"""
        # In production, would fetch from SimilarWeb API
        # For now, return mock data

        # Map symbols to domains (would be a real database)
        domain_map = {
            "AAPL": "apple.com",
            "AMZN": "amazon.com",
            "GOOGL": "google.com",
            "MSFT": "microsoft.com",
            "META": "facebook.com",
            "TSLA": "tesla.com",
            "NFLX": "netflix.com",
            "NVDA": "nvidia.com"
        }

        domain = domain_map.get(symbol, f"{symbol.lower()}.com")

        return WebTrafficData(
            symbol=symbol,
            domain=domain,
            timestamp=datetime.now(),
            monthly_visits=random.randint(10000000, 1000000000),
            monthly_visits_change_pct=random.uniform(-20, 30),
            bounce_rate=random.uniform(30, 60),
            avg_visit_duration=random.uniform(60, 300),
            pages_per_visit=random.uniform(2, 8),
            traffic_rank=random.randint(1, 10000),
            traffic_rank_change=random.randint(-500, 500)
        )

    def analyze_traffic_signal(self, data: WebTrafficData) -> Dict:
        """Analyze traffic data for trading signal"""
        # Strong growth = bullish for revenue
        if data.monthly_visits_change_pct > 20:
            signal = "BULLISH"
            description = "Strong traffic growth suggests increasing demand"
        elif data.monthly_visits_change_pct > 5:
            signal = "MILD_BULLISH"
            description = "Moderate traffic growth"
        elif data.monthly_visits_change_pct < -20:
            signal = "BEARISH"
            description = "Significant traffic decline - demand concerns"
        elif data.monthly_visits_change_pct < -5:
            signal = "MILD_BEARISH"
            description = "Moderate traffic decline"
        else:
            signal = "NEUTRAL"
            description = "Traffic stable"

        # Engagement quality
        engagement_score = (
            (100 - data.bounce_rate) * 0.3 +
            min(100, data.avg_visit_duration / 3) * 0.3 +
            min(100, data.pages_per_visit * 15) * 0.4
        )

        return {
            "symbol": data.symbol,
            "domain": data.domain,
            "monthly_visits": data.monthly_visits,
            "growth_pct": data.monthly_visits_change_pct,
            "signal": signal,
            "description": description,
            "engagement_score": engagement_score,
            "traffic_rank": data.traffic_rank
        }


class AlternativeDataEngine:
    """
    Combined alternative data engine.

    Integrates multiple non-traditional data sources
    for unique market insights.
    """

    def __init__(
        self,
        similarweb_api_key: Optional[str] = None
    ):
        self.sentiment = SentimentAnalyzer()
        self.traffic = WebTrafficAnalyzer(similarweb_api_key)

        logger.info("Alternative Data Engine initialized")

    def get_comprehensive_alt_data(self, symbol: str) -> Dict:
        """Get all alternative data for a symbol"""
        sentiment = self.sentiment.get_social_sentiment(symbol)
        trend = self.sentiment.get_sentiment_trend(symbol)
        divergence = self.sentiment.detect_sentiment_divergence(symbol)
        traffic = self.traffic.get_traffic_data(symbol)
        traffic_signal = self.traffic.analyze_traffic_signal(traffic)

        # Combine signals
        signals = []

        if sentiment.is_extreme:
            signals.append(f"EXTREME_{sentiment.signal.value.upper()}_SENTIMENT")

        if divergence and divergence.get("divergence_detected"):
            signals.append(f"{divergence['type']}_DIVERGENCE")

        if traffic_signal["signal"] in ["BULLISH", "BEARISH"]:
            signals.append(f"{traffic_signal['signal']}_TRAFFIC")

        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "sentiment": {
                "score": sentiment.raw_score,
                "signal": sentiment.signal.value,
                "volume": sentiment.volume,
                "is_extreme": sentiment.is_extreme,
                "sources": sentiment.sources
            },
            "sentiment_trend": {
                "direction": trend.trend_direction if trend else "UNKNOWN",
                "momentum": trend.momentum if trend else 0
            } if trend else None,
            "divergence": divergence,
            "web_traffic": traffic_signal,
            "combined_signals": signals,
            "actionable": len(signals) > 0
        }

    def scan_watchlist(self, watchlist: List[str]) -> List[Dict]:
        """Scan watchlist for alt data signals"""
        results = []

        for symbol in watchlist:
            data = self.get_comprehensive_alt_data(symbol)

            if data["actionable"]:
                results.append({
                    "symbol": symbol,
                    "signals": data["combined_signals"],
                    "sentiment_score": data["sentiment"]["score"],
                    "sentiment_signal": data["sentiment"]["signal"]
                })

        return sorted(results, key=lambda x: abs(x["sentiment_score"]), reverse=True)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ALTERNATIVE DATA ENGINE")
    print("=" * 60)

    engine = AlternativeDataEngine()

    # Get comprehensive data
    print("\n=== COMPREHENSIVE ALT DATA: NVDA ===")
    data = engine.get_comprehensive_alt_data("NVDA")

    print(f"\nSentiment:")
    print(f"  Score: {data['sentiment']['score']:.1f}")
    print(f"  Signal: {data['sentiment']['signal']}")
    print(f"  Volume: {data['sentiment']['volume']:,}")
    print(f"  Extreme: {data['sentiment']['is_extreme']}")

    if data['sentiment_trend']:
        print(f"\nSentiment Trend:")
        print(f"  Direction: {data['sentiment_trend']['direction']}")
        print(f"  Momentum: {data['sentiment_trend']['momentum']:.2f}")

    if data['divergence']:
        print(f"\nDivergence:")
        print(f"  Type: {data['divergence']['type']}")
        if data['divergence'].get('divergence_detected'):
            print(f"  Description: {data['divergence']['description']}")

    print(f"\nWeb Traffic:")
    print(f"  Growth: {data['web_traffic']['growth_pct']:.1f}%")
    print(f"  Signal: {data['web_traffic']['signal']}")

    print(f"\nCombined Signals: {data['combined_signals']}")

    # Scan watchlist
    print("\n=== WATCHLIST SCAN ===")
    watchlist = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
    results = engine.scan_watchlist(watchlist)

    for r in results[:5]:
        print(f"  {r['symbol']}: {r['signals']} (score: {r['sentiment_score']:.1f})")
