"""
Market Regime Detection Engine
Analyzes market conditions and classifies the trading environment
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, List
from dataclasses import dataclass
from enum import Enum


class MarketRegime(Enum):
    """Market regime classifications"""
    STRONG_TREND_UP = "Strong Trend Up"
    TREND_UP = "Trend Up"
    RANGING_BULLISH = "Ranging (Bullish Bias)"
    RANGING_NEUTRAL = "Ranging (Neutral)"
    RANGING_BEARISH = "Ranging (Bearish Bias)"
    TREND_DOWN = "Trend Down"
    STRONG_TREND_DOWN = "Strong Trend Down"
    HIGH_VOLATILITY = "High Volatility (Unstable)"
    LOW_VOLATILITY = "Low Volatility (Consolidation)"


class VolatilityRegime(Enum):
    """Volatility environment classifications"""
    EXTREME_LOW = "Extremely Low IV (VIX < 12)"
    LOW = "Low IV (VIX 12-16)"
    NORMAL = "Normal IV (VIX 16-20)"
    ELEVATED = "Elevated IV (VIX 20-30)"
    HIGH = "High IV (VIX 30-40)"
    EXTREME = "Extreme IV (VIX > 40)"


@dataclass
class MarketEnvironment:
    """Complete market environment analysis"""
    regime: MarketRegime
    volatility_regime: VolatilityRegime
    trend_strength: float  # 0-100
    volatility_percentile: float  # 0-100
    gamma_regime: str  # "Positive" or "Negative"
    iv_rank: float  # 0-100
    confidence: float  # 0-100
    key_levels: Dict[str, float]
    raw_metrics: Dict[str, float]


class MarketRegimeDetector:
    """Detects market regime using multiple indicators"""
    
    def __init__(self):
        self.lookback_short = 20
        self.lookback_medium = 50
        self.lookback_long = 200
    
    def analyze_environment(
        self, 
        ohlc: pd.DataFrame,
        gex_data: pd.DataFrame = None,
        zero_gamma: float = None,
        current_price: float = None,
        vix: float = None
    ) -> MarketEnvironment:
        """
        Comprehensive market environment analysis
        
        Args:
            ohlc: OHLC price data
            gex_data: Gamma exposure data
            zero_gamma: Zero gamma level
            current_price: Current spot price
            vix: VIX level
            
        Returns:
            MarketEnvironment with complete analysis
        """
        if current_price is None:
            current_price = ohlc['Close'].iloc[-1]
        
        # Calculate all metrics
        metrics = self._calculate_metrics(ohlc, current_price, vix)
        
        # Determine regimes
        market_regime = self._classify_market_regime(metrics)
        vol_regime = self._classify_volatility_regime(metrics, vix)
        gamma_regime = self._classify_gamma_regime(current_price, zero_gamma)
        
        # Calculate confidence
        confidence = self._calculate_confidence(metrics)
        
        # Identify key levels
        key_levels = self._identify_key_levels(ohlc, zero_gamma)
        
        return MarketEnvironment(
            regime=market_regime,
            volatility_regime=vol_regime,
            trend_strength=metrics['trend_strength'],
            volatility_percentile=metrics['vol_percentile'],
            gamma_regime=gamma_regime,
            iv_rank=metrics['iv_rank'],
            confidence=confidence,
            key_levels=key_levels,
            raw_metrics=metrics
        )
    
    def _calculate_metrics(
        self, 
        ohlc: pd.DataFrame, 
        current_price: float,
        vix: float = None
    ) -> Dict[str, float]:
        """Calculate all technical metrics"""
        close = ohlc['Close']
        high = ohlc['High']
        low = ohlc['Low']
        
        # Moving averages
        sma20 = close.rolling(20).mean().iloc[-1]
        sma50 = close.rolling(50).mean().iloc[-1]
        sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else sma50
        
        # Trend metrics
        adx = self._calculate_adx(ohlc)
        
        # Price position relative to MAs
        price_vs_sma20 = ((current_price / sma20) - 1) * 100
        price_vs_sma50 = ((current_price / sma50) - 1) * 100
        price_vs_sma200 = ((current_price / sma200) - 1) * 100
        
        # Volatility metrics
        atr20 = self._calculate_atr(ohlc, 20)
        atr_pct = (atr20 / current_price) * 100
        
        historical_vol = close.pct_change().rolling(20).std() * np.sqrt(252) * 100
        hv = historical_vol.iloc[-1]
        
        # Volatility percentile (last 252 days)
        vol_percentile = (historical_vol.iloc[-1] > historical_vol.iloc[-252:]).sum() / 252 * 100 if len(historical_vol) >= 252 else 50
        
        # IV Rank (if VIX provided)
        if vix is not None:
            # Using VIX as proxy for IV
            vix_series = pd.Series([vix] * 252)  # Simplified
            iv_rank = 50  # Placeholder - would need historical VIX data
        else:
            iv_rank = 50
        
        # Momentum
        roc20 = ((close.iloc[-1] / close.iloc[-20]) - 1) * 100 if len(close) >= 20 else 0
        
        # MA alignment for trend
        ma_alignment = 0
        if sma20 > sma50:
            ma_alignment += 1
        if sma50 > sma200:
            ma_alignment += 1
        if sma20 > sma200:
            ma_alignment += 1
        
        # MA bearish alignment
        ma_bear_alignment = 0
        if sma20 < sma50:
            ma_bear_alignment += 1
        if sma50 < sma200:
            ma_bear_alignment += 1
        if sma20 < sma200:
            ma_bear_alignment += 1
        
        # Trend strength (0-100)
        trend_strength = min(100, max(0, (
            (adx * 2) +  # ADX weighted heavily
            (abs(price_vs_sma20) * 2) +
            (ma_alignment * 10) +
            (abs(roc20))
        ) / 2))
        
        return {
            'current_price': current_price,
            'sma20': sma20,
            'sma50': sma50,
            'sma200': sma200,
            'price_vs_sma20': price_vs_sma20,
            'price_vs_sma50': price_vs_sma50,
            'price_vs_sma200': price_vs_sma200,
            'adx': adx,
            'atr20': atr20,
            'atr_pct': atr_pct,
            'hv': hv,
            'vol_percentile': vol_percentile,
            'iv_rank': iv_rank,
            'roc20': roc20,
            'ma_alignment': ma_alignment,
            'ma_bear_alignment': ma_bear_alignment,
            'trend_strength': trend_strength,
            'vix': vix or 20,  # Default VIX
        }
    
    def _calculate_adx(self, ohlc: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average Directional Index"""
        high = ohlc['High']
        low = ohlc['Low']
        close = ohlc['Close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        # Directional Movement
        up_move = high - high.shift()
        down_move = low.shift() - low
        
        pos_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        neg_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        pos_di = 100 * pd.Series(pos_dm).rolling(period).mean() / atr
        neg_di = 100 * pd.Series(neg_dm).rolling(period).mean() / atr
        
        dx = 100 * abs(pos_di - neg_di) / (pos_di + neg_di)
        adx = dx.rolling(period).mean()
        
        return adx.iloc[-1] if not adx.empty else 20
    
    def _calculate_atr(self, ohlc: pd.DataFrame, period: int = 20) -> float:
        """Calculate Average True Range"""
        high = ohlc['High']
        low = ohlc['Low']
        close = ohlc['Close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(period).mean()
        return atr.iloc[-1]
    
    def _classify_market_regime(self, metrics: Dict[str, float]) -> MarketRegime:
        """Classify the market regime based on metrics"""
        price_vs_sma20 = metrics['price_vs_sma20']
        price_vs_sma50 = metrics['price_vs_sma50']
        adx = metrics['adx']
        ma_alignment = metrics['ma_alignment']
        ma_bear_alignment = metrics['ma_bear_alignment']
        roc20 = metrics['roc20']
        
        # Strong trends
        if adx > 40 and price_vs_sma20 > 3 and ma_alignment >= 2:
            return MarketRegime.STRONG_TREND_UP
        if adx > 40 and price_vs_sma20 < -3 and ma_bear_alignment >= 2:
            return MarketRegime.STRONG_TREND_DOWN
        
        # Moderate trends
        if adx > 25 and price_vs_sma20 > 1.5 and ma_alignment >= 1:
            return MarketRegime.TREND_UP
        if adx > 25 and price_vs_sma20 < -1.5 and ma_bear_alignment >= 1:
            return MarketRegime.TREND_DOWN
        
        # High volatility (choppy)
        if metrics['vol_percentile'] > 75 and adx < 20:
            return MarketRegime.HIGH_VOLATILITY
        
        # Low volatility
        if metrics['vol_percentile'] < 25 and adx < 15:
            return MarketRegime.LOW_VOLATILITY
        
        # Ranging markets
        if abs(price_vs_sma20) < 1.5 and adx < 25:
            if roc20 > 2:
                return MarketRegime.RANGING_BULLISH
            elif roc20 < -2:
                return MarketRegime.RANGING_BEARISH
            else:
                return MarketRegime.RANGING_NEUTRAL
        
        # Default to ranging neutral
        return MarketRegime.RANGING_NEUTRAL
    
    def _classify_volatility_regime(
        self, 
        metrics: Dict[str, float],
        vix: float = None
    ) -> VolatilityRegime:
        """Classify volatility regime"""
        if vix is None:
            vix = metrics.get('vix', 20)
        
        if vix < 12:
            return VolatilityRegime.EXTREME_LOW
        elif vix < 16:
            return VolatilityRegime.LOW
        elif vix < 20:
            return VolatilityRegime.NORMAL
        elif vix < 30:
            return VolatilityRegime.ELEVATED
        elif vix < 40:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.EXTREME
    
    def _classify_gamma_regime(
        self, 
        current_price: float,
        zero_gamma: float = None
    ) -> str:
        """Determine if we're in positive or negative gamma"""
        if zero_gamma is None:
            return "Unknown"
        
        if current_price > zero_gamma:
            return "Positive Gamma (Dealers Short)"
        else:
            return "Negative Gamma (Dealers Long)"
    
    def _calculate_confidence(self, metrics: Dict[str, float]) -> float:
        """Calculate confidence in regime classification"""
        # Higher ADX = higher confidence in trend
        adx_confidence = min(100, metrics['adx'] * 2)
        
        # MA alignment adds confidence
        ma_confidence = (metrics['ma_alignment'] + metrics['ma_bear_alignment']) / 3 * 100
        
        # Strong price deviation adds confidence
        price_deviation = abs(metrics['price_vs_sma20'])
        deviation_confidence = min(100, price_deviation * 10)
        
        # Average the confidences
        confidence = (adx_confidence + ma_confidence + deviation_confidence) / 3
        
        return min(100, max(20, confidence))  # Clamp between 20-100
    
    def _identify_key_levels(
        self, 
        ohlc: pd.DataFrame,
        zero_gamma: float = None
    ) -> Dict[str, float]:
        """Identify key support/resistance levels"""
        close = ohlc['Close']
        high = ohlc['High']
        low = ohlc['Low']
        
        current_price = close.iloc[-1]
        
        # Recent swing highs/lows
        recent_high = high.iloc[-20:].max()
        recent_low = low.iloc[-20:].min()
        
        # Longer-term levels
        swing_high_50 = high.iloc[-50:].max() if len(high) >= 50 else recent_high
        swing_low_50 = low.iloc[-50:].min() if len(low) >= 50 else recent_low
        
        levels = {
            'current_price': current_price,
            'recent_high': recent_high,
            'recent_low': recent_low,
            'swing_high_50': swing_high_50,
            'swing_low_50': swing_low_50,
            'sma20': close.rolling(20).mean().iloc[-1],
            'sma50': close.rolling(50).mean().iloc[-1],
        }
        
        if zero_gamma is not None:
            levels['zero_gamma'] = zero_gamma
        
        return levels
