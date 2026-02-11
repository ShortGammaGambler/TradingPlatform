"""
Options Strategy Recommendation Engine
AI-powered strategy selection with confidence scoring
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from src.core.market_regime import MarketEnvironment, MarketRegime, VolatilityRegime


@dataclass
class StrategyRecommendation:
    """A recommended options strategy"""
    name: str
    type: str  # "Bullish", "Bearish", "Neutral", "Volatility"
    confidence: float  # 0-100
    reasoning: str
    strikes: Dict[str, float]
    expiration_dte: int  # Days to expiration
    risk_reward: str
    max_profit: str
    max_loss: str
    breakeven: List[float]
    greeks_profile: str
    market_conditions: str
    pros: List[str]
    cons: List[str]


class StrategyEngine:
    """
    Recommends optimal options strategies based on market environment
    """
    
    STRATEGIES = {
        # Bullish Strategies
        'long_call': {
            'name': 'Long Call',
            'type': 'Bullish',
            'regimes': [MarketRegime.TREND_UP, MarketRegime.STRONG_TREND_UP],
            'vol_regimes': [VolatilityRegime.LOW, VolatilityRegime.NORMAL],
        },
        'bull_call_spread': {
            'name': 'Bull Call Spread (Vertical)',
            'type': 'Bullish',
            'regimes': [MarketRegime.TREND_UP, MarketRegime.RANGING_BULLISH],
            'vol_regimes': [VolatilityRegime.NORMAL, VolatilityRegime.ELEVATED],
        },
        'bull_put_spread': {
            'name': 'Bull Put Spread (Credit Spread)',
            'type': 'Bullish',
            'regimes': [MarketRegime.RANGING_BULLISH, MarketRegime.TREND_UP],
            'vol_regimes': [VolatilityRegime.ELEVATED, VolatilityRegime.HIGH],
        },
        'calendar_call': {
            'name': 'Call Calendar Spread',
            'type': 'Neutral-Bullish',
            'regimes': [MarketRegime.RANGING_BULLISH, MarketRegime.RANGING_NEUTRAL],
            'vol_regimes': [VolatilityRegime.LOW, VolatilityRegime.NORMAL],
        },
        
        # Bearish Strategies
        'long_put': {
            'name': 'Long Put',
            'type': 'Bearish',
            'regimes': [MarketRegime.TREND_DOWN, MarketRegime.STRONG_TREND_DOWN],
            'vol_regimes': [VolatilityRegime.LOW, VolatilityRegime.NORMAL],
        },
        'bear_put_spread': {
            'name': 'Bear Put Spread (Vertical)',
            'type': 'Bearish',
            'regimes': [MarketRegime.TREND_DOWN, MarketRegime.RANGING_BEARISH],
            'vol_regimes': [VolatilityRegime.NORMAL, VolatilityRegime.ELEVATED],
        },
        'bear_call_spread': {
            'name': 'Bear Call Spread (Credit Spread)',
            'type': 'Bearish',
            'regimes': [MarketRegime.RANGING_BEARISH, MarketRegime.TREND_DOWN],
            'vol_regimes': [VolatilityRegime.ELEVATED, VolatilityRegime.HIGH],
        },
        
        # Neutral Strategies
        'iron_condor': {
            'name': 'Iron Condor',
            'type': 'Neutral',
            'regimes': [MarketRegime.RANGING_NEUTRAL, MarketRegime.LOW_VOLATILITY],
            'vol_regimes': [VolatilityRegime.ELEVATED, VolatilityRegime.HIGH],
        },
        'iron_butterfly': {
            'name': 'Iron Butterfly',
            'type': 'Neutral',
            'regimes': [MarketRegime.RANGING_NEUTRAL, MarketRegime.LOW_VOLATILITY],
            'vol_regimes': [VolatilityRegime.ELEVATED, VolatilityRegime.HIGH],
        },
        'short_strangle': {
            'name': 'Short Strangle',
            'type': 'Neutral',
            'regimes': [MarketRegime.RANGING_NEUTRAL, MarketRegime.LOW_VOLATILITY],
            'vol_regimes': [VolatilityRegime.ELEVATED, VolatilityRegime.HIGH, VolatilityRegime.EXTREME],
        },
        'jade_lizard': {
            'name': 'Jade Lizard',
            'type': 'Neutral-Bullish',
            'regimes': [MarketRegime.RANGING_BULLISH, MarketRegime.RANGING_NEUTRAL],
            'vol_regimes': [VolatilityRegime.ELEVATED, VolatilityRegime.HIGH],
        },
        
        # Volatility Strategies
        'long_straddle': {
            'name': 'Long Straddle',
            'type': 'High Volatility Expected',
            'regimes': [MarketRegime.LOW_VOLATILITY],
            'vol_regimes': [VolatilityRegime.EXTREME_LOW, VolatilityRegime.LOW],
        },
        'long_strangle': {
            'name': 'Long Strangle',
            'type': 'High Volatility Expected',
            'regimes': [MarketRegime.LOW_VOLATILITY],
            'vol_regimes': [VolatilityRegime.EXTREME_LOW, VolatilityRegime.LOW],
        },
        'butterfly_spread': {
            'name': 'Long Butterfly Spread',
            'type': 'Neutral',
            'regimes': [MarketRegime.RANGING_NEUTRAL],
            'vol_regimes': [VolatilityRegime.NORMAL, VolatilityRegime.ELEVATED],
        },
        
        # Advanced/Ratio Strategies
        'call_ratio_spread': {
            'name': 'Call Ratio Back Spread',
            'type': 'Bullish-Volatility',
            'regimes': [MarketRegime.RANGING_BULLISH, MarketRegime.TREND_UP],
            'vol_regimes': [VolatilityRegime.LOW, VolatilityRegime.NORMAL],
        },
        'put_ratio_spread': {
            'name': 'Put Ratio Back Spread',
            'type': 'Bearish-Volatility',
            'regimes': [MarketRegime.RANGING_BEARISH, MarketRegime.TREND_DOWN],
            'vol_regimes': [VolatilityRegime.LOW, VolatilityRegime.NORMAL],
        },
    }
    
    def __init__(self):
        pass
    
    def recommend_strategies(
        self, 
        market_env: MarketEnvironment,
        current_price: float,
        num_recommendations: int = 5
    ) -> List[StrategyRecommendation]:
        """
        Generate ranked strategy recommendations based on market environment
        
        Args:
            market_env: Current market environment analysis
            current_price: Current underlying price
            num_recommendations: Number of top strategies to return
            
        Returns:
            List of recommended strategies with confidence scores
        """
        recommendations = []
        
        for strategy_id, strategy_info in self.STRATEGIES.items():
            # Calculate match score
            confidence = self._calculate_confidence(
                strategy_info,
                market_env
            )
            
            # Only include strategies with meaningful confidence
            if confidence >= 30:
                recommendation = self._build_recommendation(
                    strategy_id,
                    strategy_info,
                    market_env,
                    current_price,
                    confidence
                )
                recommendations.append(recommendation)
        
        # Sort by confidence
        recommendations.sort(key=lambda x: x.confidence, reverse=True)
        
        return recommendations[:num_recommendations]
    
    def _calculate_confidence(
        self,
        strategy_info: Dict,
        market_env: MarketEnvironment
    ) -> float:
        """Calculate confidence score for a strategy given market conditions"""
        base_confidence = 0
        
        # Regime match (60% weight)
        regime_match = strategy_info['regimes']
        if market_env.regime in regime_match:
            regime_score = 60
        else:
            # Partial credit for related regimes
            regime_score = 20
        
        # Volatility regime match (30% weight)
        vol_match = strategy_info['vol_regimes']
        if market_env.volatility_regime in vol_match:
            vol_score = 30
        else:
            vol_score = 10
        
        # Market environment confidence (10% weight)
        env_confidence = market_env.confidence / 10
        
        confidence = regime_score + vol_score + env_confidence
        
        # Adjust based on trend strength for directional strategies
        if 'Bullish' in strategy_info['type'] or 'Bearish' in strategy_info['type']:
            if market_env.trend_strength > 60:
                confidence *= 1.2  # Boost for strong trends
            elif market_env.trend_strength < 30:
                confidence *= 0.8  # Reduce for weak trends
        
        return min(100, max(0, confidence))
    
    def _build_recommendation(
        self,
        strategy_id: str,
        strategy_info: Dict,
        market_env: MarketEnvironment,
        current_price: float,
        confidence: float
    ) -> StrategyRecommendation:
        """Build detailed strategy recommendation"""
        
        # Calculate strikes based on strategy type and current price
        strikes = self._calculate_strikes(strategy_id, current_price, market_env)
        
        # Determine optimal expiration
        dte = self._determine_expiration(strategy_id, market_env)
        
        # Build reasoning
        reasoning = self._build_reasoning(strategy_id, market_env)
        
        # Get strategy details
        details = self._get_strategy_details(strategy_id, strikes, current_price)
        
        return StrategyRecommendation(
            name=strategy_info['name'],
            type=strategy_info['type'],
            confidence=round(confidence, 1),
            reasoning=reasoning,
            strikes=strikes,
            expiration_dte=dte,
            risk_reward=details['risk_reward'],
            max_profit=details['max_profit'],
            max_loss=details['max_loss'],
            breakeven=details['breakeven'],
            greeks_profile=details['greeks_profile'],
            market_conditions=details['market_conditions'],
            pros=details['pros'],
            cons=details['cons']
        )
    
    def _calculate_strikes(
        self,
        strategy_id: str,
        current_price: float,
        market_env: MarketEnvironment
    ) -> Dict[str, float]:
        """Calculate optimal strike prices for strategy"""
        
        atr_pct = market_env.raw_metrics.get('atr_pct', 2.0)
        
        strikes = {}
        
        if strategy_id == 'long_call':
            strikes['long_call'] = round(current_price * 1.02, 2)
            
        elif strategy_id == 'bull_call_spread':
            strikes['long_call'] = round(current_price * 0.98, 2)
            strikes['short_call'] = round(current_price * 1.05, 2)
            
        elif strategy_id == 'bull_put_spread':
            strikes['short_put'] = round(current_price * 0.97, 2)
            strikes['long_put'] = round(current_price * 0.92, 2)
            
        elif strategy_id == 'long_put':
            strikes['long_put'] = round(current_price * 0.98, 2)
            
        elif strategy_id == 'bear_put_spread':
            strikes['long_put'] = round(current_price * 1.02, 2)
            strikes['short_put'] = round(current_price * 0.95, 2)
            
        elif strategy_id == 'bear_call_spread':
            strikes['short_call'] = round(current_price * 1.03, 2)
            strikes['long_call'] = round(current_price * 1.08, 2)
            
        elif strategy_id == 'iron_condor':
            strikes['short_put'] = round(current_price * 0.95, 2)
            strikes['long_put'] = round(current_price * 0.90, 2)
            strikes['short_call'] = round(current_price * 1.05, 2)
            strikes['long_call'] = round(current_price * 1.10, 2)
            
        elif strategy_id == 'iron_butterfly':
            strikes['short_put'] = round(current_price, 2)
            strikes['long_put'] = round(current_price * 0.95, 2)
            strikes['short_call'] = round(current_price, 2)
            strikes['long_call'] = round(current_price * 1.05, 2)
            
        elif strategy_id == 'short_strangle':
            strikes['short_put'] = round(current_price * 0.95, 2)
            strikes['short_call'] = round(current_price * 1.05, 2)
            
        elif strategy_id == 'jade_lizard':
            strikes['short_put'] = round(current_price * 0.95, 2)
            strikes['short_call'] = round(current_price * 1.05, 2)
            strikes['long_call'] = round(current_price * 1.10, 2)
            
        elif strategy_id == 'long_straddle':
            strikes['long_call'] = round(current_price, 2)
            strikes['long_put'] = round(current_price, 2)
            
        elif strategy_id == 'long_strangle':
            strikes['long_call'] = round(current_price * 1.03, 2)
            strikes['long_put'] = round(current_price * 0.97, 2)
            
        elif strategy_id == 'butterfly_spread':
            strikes['long_call_lower'] = round(current_price * 0.97, 2)
            strikes['short_call_mid'] = round(current_price, 2)
            strikes['long_call_upper'] = round(current_price * 1.03, 2)
            
        elif strategy_id == 'call_ratio_spread':
            strikes['long_call'] = round(current_price * 1.02, 2)
            strikes['short_call'] = round(current_price * 1.07, 2)
            
        elif strategy_id == 'put_ratio_spread':
            strikes['long_put'] = round(current_price * 0.98, 2)
            strikes['short_put'] = round(current_price * 0.93, 2)
            
        elif strategy_id == 'calendar_call':
            strikes['short_call_near'] = round(current_price * 1.02, 2)
            strikes['long_call_far'] = round(current_price * 1.02, 2)
        
        return strikes
    
    def _determine_expiration(
        self,
        strategy_id: str,
        market_env: MarketEnvironment
    ) -> int:
        """Determine optimal days to expiration"""
        
        # Calendar spreads need specific handling
        if 'calendar' in strategy_id:
            return 30  # Near term leg
        
        # High IV environments favor shorter expirations
        if market_env.volatility_regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]:
            if 'spread' in strategy_id or 'condor' in strategy_id:
                return 30  # 30-45 DTE for credit strategies
            else:
                return 20
        
        # Low IV environments favor longer expirations for long premium
        if market_env.volatility_regime in [VolatilityRegime.EXTREME_LOW, VolatilityRegime.LOW]:
            if 'long' in strategy_id:
                return 60  # LEAPS-style for long options
            else:
                return 45
        
        # Default to 45 DTE (sweet spot for many strategies)
        return 45
    
    def _build_reasoning(
        self,
        strategy_id: str,
        market_env: MarketEnvironment
    ) -> str:
        """Build explanation for why this strategy is recommended"""
        
        regime_name = market_env.regime.value
        vol_regime = market_env.volatility_regime.value
        gamma = market_env.gamma_regime
        
        reasoning = f"Market is in {regime_name} with {vol_regime}. "
        reasoning += f"Gamma regime: {gamma}. "
        reasoning += f"Trend strength: {market_env.trend_strength:.0f}/100. "
        
        # Strategy-specific reasoning
        if 'bull' in strategy_id.lower():
            reasoning += "Bullish setup capitalizes on upward price movement. "
        elif 'bear' in strategy_id.lower():
            reasoning += "Bearish setup profits from downward price movement. "
        elif 'condor' in strategy_id or 'butterfly' in strategy_id:
            reasoning += "Range-bound strategy benefits from price staying within range. "
        elif 'straddle' in strategy_id or 'strangle' in strategy_id:
            if 'long' in strategy_id:
                reasoning += "Volatility expansion expected - benefits from large moves. "
            else:
                reasoning += "Volatility contraction expected - profits from stable prices. "
        
        return reasoning
    
    def _get_strategy_details(
        self,
        strategy_id: str,
        strikes: Dict[str, float],
        current_price: float
    ) -> Dict:
        """Get detailed information about strategy characteristics"""
        
        # This is a simplified version - in production, you'd calculate precise Greeks
        details = {
            'risk_reward': 'Defined',
            'max_profit': 'Limited',
            'max_loss': 'Limited',
            'breakeven': [current_price],
            'greeks_profile': 'Positive Theta',
            'market_conditions': 'Neutral to Bullish',
            'pros': [],
            'cons': []
        }
        
        # Customize based on strategy
        if 'long_call' == strategy_id:
            details.update({
                'risk_reward': 'Asymmetric (Limited Risk, Unlimited Profit)',
                'max_profit': 'Unlimited',
                'max_loss': 'Premium Paid',
                'breakeven': [strikes.get('long_call', current_price)],
                'greeks_profile': 'Positive Delta, Long Vega, Negative Theta',
                'pros': ['Unlimited upside', 'Limited risk', 'Leveraged exposure'],
                'cons': ['Time decay', 'Requires significant move', 'High cost in high IV']
            })
        
        elif 'spread' in strategy_id and 'bull' in strategy_id:
            details.update({
                'risk_reward': 'Defined (Limited Risk, Limited Profit)',
                'max_profit': 'Width of spread - Net Debit',
                'max_loss': 'Net Debit Paid',
                'greeks_profile': 'Positive Delta, Negative Theta (initially)',
                'pros': ['Lower cost than long call', 'Defined risk', 'Better probability'],
                'cons': ['Limited profit potential', 'Still requires upward movement']
            })
        
        elif 'iron_condor' == strategy_id:
            details.update({
                'risk_reward': 'Defined (Limited Risk, Limited Profit)',
                'max_profit': 'Net Credit Received',
                'max_loss': 'Width of widest spread - Net Credit',
                'greeks_profile': 'Market Neutral, Positive Theta, Short Vega',
                'pros': ['High probability', 'Theta decay works for you', 'Profits in range'],
                'cons': ['Limited profit', 'Requires active management', 'Multiple legs']
            })
        
        elif 'jade_lizard' == strategy_id:
            details.update({
                'risk_reward': 'Undefined upside risk, Defined downside',
                'max_profit': 'Net Credit Received',
                'max_loss': 'Substantial on downside',
                'greeks_profile': 'Positive Theta, Short Vega, Slight Bullish Delta',
                'pros': ['No upside risk if structured correctly', 'High premium collection', 'Theta positive'],
                'cons': ['Unlimited downside risk', 'Complex management', 'Requires high IV']
            })
        
        elif 'straddle' in strategy_id and 'long' in strategy_id:
            details.update({
                'risk_reward': 'Limited Risk, Unlimited Profit (both directions)',
                'max_profit': 'Unlimited',
                'max_loss': 'Total Premium Paid',
                'greeks_profile': 'Market Neutral Delta, Long Vega, Negative Theta',
                'pros': ['Profits from big moves either direction', 'No directional bias needed'],
                'cons': ['Expensive', 'Requires large move to profit', 'Heavy theta decay']
            })
        
        # Add more strategy-specific details as needed
        
        return details
