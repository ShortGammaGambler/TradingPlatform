"""
Gamma-Based Trading Strategies
Collection of strategies that trade based on gamma exposure and regime.
"""

from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from src.backtesting.backtest_engine import MarketState, Portfolio, Trade, GammaRegime


# =============================================================================
# STRATEGY 1: Gamma Flip Breakout
# =============================================================================

def gamma_flip_breakout(market_state: MarketState, portfolio: Portfolio) -> Optional[Trade]:
    """
    Trade breakouts through the gamma flip level.

    Logic:
    - When price breaks ABOVE gamma flip from negative gamma -> expect acceleration UP
    - When price breaks BELOW gamma flip from positive gamma -> expect acceleration DOWN

    This exploits the transition from stabilizing to amplifying dealer flows.
    """
    distance = market_state.distance_to_flip
    flip = market_state.gamma_flip_level
    spot = market_state.spot_price

    # Check if we already have a position from this strategy
    existing = [p for p in portfolio.positions if p.strategy == 'gamma_flip_breakout']
    if existing:
        return None

    # LONG: Breaking above flip from negative gamma
    if (0 < distance < 0.5 and  # Just crossed above
        market_state.regime == GammaRegime.NEGATIVE and
        market_state.total_gex < 0):

        atr_estimate = spot * 0.01  # Rough 1% daily range
        stop = flip * 0.995  # Stop just below flip
        target = spot + (spot - stop) * 2  # 2:1 R/R

        return Trade(
            entry_time=market_state.timestamp,
            entry_price=spot,
            direction='long',
            size=1,
            instrument='SPY',
            strategy='gamma_flip_breakout',
            stop_loss=stop,
            take_profit=target
        )

    # SHORT: Breaking below flip from positive gamma
    if (-0.5 < distance < 0 and  # Just crossed below
        market_state.regime == GammaRegime.POSITIVE and
        market_state.total_gex > 0):

        stop = flip * 1.005  # Stop just above flip
        target = spot - (stop - spot) * 2  # 2:1 R/R

        return Trade(
            entry_time=market_state.timestamp,
            entry_price=spot,
            direction='short',
            size=1,
            instrument='SPY',
            strategy='gamma_flip_breakout',
            stop_loss=stop,
            take_profit=target
        )

    return None


# =============================================================================
# STRATEGY 2: Deep Negative Gamma Mean Reversion
# =============================================================================

def deep_negative_gamma_reversion(market_state: MarketState, portfolio: Portfolio) -> Optional[Trade]:
    """
    Mean reversion in deep negative gamma environments.

    Logic:
    - Deep negative gamma = dealers amplifying moves = overextension likely
    - When price extends >2% below gamma flip in deep neg gamma, expect snapback
    - High IV rank confirms elevated fear / overreaction
    - Target the gamma flip level (where flows normalize)

    Risk: This is counter-trend; requires strict stops.
    """
    existing = [p for p in portfolio.positions if p.strategy == 'deep_negative_gamma_reversion']
    if existing:
        return None

    distance = market_state.distance_to_flip

    # LONG: Extended below flip in fear environment
    if (distance < -2.0 and  # More than 2% below flip
        market_state.regime == GammaRegime.DEEP_NEGATIVE and
        market_state.iv_rank > 60 and  # Fear elevated
        market_state.vol_premium > 5):  # Options expensive (IV > RV)

        spot = market_state.spot_price
        stop = spot * 0.97  # 3% stop (wide for vol)
        target = market_state.gamma_flip_level * 0.995  # Just below flip

        return Trade(
            entry_time=market_state.timestamp,
            entry_price=spot,
            direction='long',
            size=1,
            instrument='SPY',
            strategy='deep_negative_gamma_reversion',
            stop_loss=stop,
            take_profit=target
        )

    return None


# =============================================================================
# STRATEGY 3: Positive Gamma Range Fade
# =============================================================================

def positive_gamma_range_fade(market_state: MarketState, portfolio: Portfolio) -> Optional[Trade]:
    """
    Fade moves in positive gamma environments.

    Logic:
    - Positive gamma = dealer hedging OPPOSES price moves
    - Price tends to get "pinned" near high gamma strikes
    - Fade extensions in either direction
    - Low IV rank = complacency, good for selling premium

    Implementation:
    - If price extends up in positive gamma -> short
    - If price extends down in positive gamma -> long
    """
    existing = [p for p in portfolio.positions if p.strategy == 'positive_gamma_range_fade']
    if existing:
        return None

    distance = market_state.distance_to_flip

    # Only trade in positive gamma with low IV
    if market_state.regime not in [GammaRegime.POSITIVE, GammaRegime.DEEP_POSITIVE]:
        return None

    if market_state.iv_rank > 50:  # Want low IV for this strategy
        return None

    spot = market_state.spot_price
    flip = market_state.gamma_flip_level

    # FADE LONG (short when extended up)
    if distance > 1.5:  # Extended above flip
        stop = spot * 1.01  # 1% stop
        target = flip  # Target the flip

        return Trade(
            entry_time=market_state.timestamp,
            entry_price=spot,
            direction='short',
            size=1,
            instrument='SPY',
            strategy='positive_gamma_range_fade',
            stop_loss=stop,
            take_profit=target
        )

    # FADE SHORT (long when extended down but still positive gamma)
    if 0 < distance < 0.5 and market_state.total_gex > 2:  # Near flip but strong positive gex
        stop = flip * 0.99
        target = spot + (spot - stop) * 1.5

        return Trade(
            entry_time=market_state.timestamp,
            entry_price=spot,
            direction='long',
            size=1,
            instrument='SPY',
            strategy='positive_gamma_range_fade',
            stop_loss=stop,
            take_profit=target
        )

    return None


# =============================================================================
# STRATEGY 4: Vol Regime Transition
# =============================================================================

def vol_regime_transition(market_state: MarketState, portfolio: Portfolio) -> Optional[Trade]:
    """
    Trade volatility regime transitions.

    Strategy Logic:
    ---------------
    1. HIGH IV (>70) + NEGATIVE GAMMA: Vol spike with dealer amplification
       - Market likely oversold, expect mean reversion bounce
       - Go LONG with wider stops (vol is elevated)

    2. LOW IV (<25) + DEEP POSITIVE GAMMA: Complacent pinned market
       - Vol likely to expand eventually
       - Breakout trade: go LONG anticipating vol expansion move

    3. IV RANK MID-ZONE (40-55) with vol premium divergence:
       - Rising vol: expect directional move, trade with gamma bias
       - Falling vol: fade extremes back toward flip

    Risk/Reward:
    - High IV trades: 4% stop, 3% target (tighter RR due to vol)
    - Low IV trades: 2% stop, 4% target (wider RR on breakouts)
    """
    existing = [p for p in portfolio.positions if p.strategy == 'vol_regime_transition']
    if existing:
        return None

    spot = market_state.spot_price
    iv_rank = market_state.iv_rank
    vol_premium = market_state.vol_premium  # IV - RV
    distance = market_state.distance_to_flip

    # SCENARIO 1: HIGH IV + NEGATIVE GAMMA = Mean reversion after vol spike
    if iv_rank > 70 and market_state.regime in [GammaRegime.NEGATIVE, GammaRegime.DEEP_NEGATIVE]:
        # Vol has spiked and market is in negative gamma
        # If price is significantly below gamma flip, expect snapback
        if distance < -1.5:
            # Wide stop due to high vol environment
            stop = spot * 0.96
            target = spot * 1.03

            return Trade(
                entry_time=market_state.timestamp,
                entry_price=spot,
                direction='long',
                size=1,
                instrument='SPY',
                strategy='vol_regime_transition',
                stop_loss=stop,
                take_profit=target
            )

    # SCENARIO 2: LOW IV + DEEP POSITIVE GAMMA = Complacent pinned market
    if iv_rank < 25 and market_state.regime == GammaRegime.DEEP_POSITIVE:
        # Low volatility, strong positive gamma
        # Market is "pinned" by dealer hedging flows
        # Vol likely to expand - prepare for breakout

        # Only trade if vol premium is negative (options cheap)
        if vol_premium < -2:
            # Price extended above flip in positive gamma
            # When vol expands, likely to continue higher
            if distance > 1.0:
                stop = spot * 0.98
                target = spot * 1.04

                return Trade(
                    entry_time=market_state.timestamp,
                    entry_price=spot,
                    direction='long',
                    size=1,
                    instrument='SPY',
                    strategy='vol_regime_transition',
                    stop_loss=stop,
                    take_profit=target
                )

    # SCENARIO 3: Rising volatility in negative gamma
    if 45 <= iv_rank <= 55 and vol_premium > 3:
        # Vol expanding from low levels
        # If in negative gamma, expect acceleration down
        if market_state.regime == GammaRegime.NEGATIVE and distance < -0.5:
            stop = spot * 1.02
            target = spot * 0.96

            return Trade(
                entry_time=market_state.timestamp,
                entry_price=spot,
                direction='short',
                size=1,
                instrument='SPY',
                strategy='vol_regime_transition',
                stop_loss=stop,
                take_profit=target
            )

    # SCENARIO 4: Falling volatility - fade extremes
    if 40 <= iv_rank <= 50 and vol_premium < 0:
        # Vol contracting - market stabilizing
        # If in positive gamma and extended, fade toward flip
        if market_state.regime == GammaRegime.POSITIVE and distance > 1.5:
            stop = spot * 1.015
            target = market_state.gamma_flip_level

            return Trade(
                entry_time=market_state.timestamp,
                entry_price=spot,
                direction='short',
                size=1,
                instrument='SPY',
                strategy='vol_regime_transition',
                stop_loss=stop,
                take_profit=target
            )

    return None


# =============================================================================
# STRATEGY 5: GEX Momentum
# =============================================================================

def gex_momentum(market_state: MarketState, portfolio: Portfolio) -> Optional[Trade]:
    """
    Trade with momentum when GEX confirms direction.

    Logic:
    - Strong positive GEX + price above flip = bullish momentum
    - Strong negative GEX + price below flip = bearish momentum
    - Use total GEX magnitude as conviction filter

    This is a trend-following approach that aligns with dealer flows.
    """
    existing = [p for p in portfolio.positions if p.strategy == 'gex_momentum']
    if existing:
        return None

    gex = market_state.total_gex
    distance = market_state.distance_to_flip
    spot = market_state.spot_price

    # BULLISH: High positive GEX, above flip, trending up
    if gex > 5 and distance > 1.0 and market_state.iv_rank < 50:
        stop = spot * 0.985  # 1.5% trailing concept
        target = spot * 1.02  # 2% target

        return Trade(
            entry_time=market_state.timestamp,
            entry_price=spot,
            direction='long',
            size=1,
            instrument='SPY',
            strategy='gex_momentum',
            stop_loss=stop,
            take_profit=target
        )

    # BEARISH: High negative GEX, below flip, trending down
    if gex < -5 and distance < -1.0 and market_state.iv_rank > 40:
        stop = spot * 1.015
        target = spot * 0.98

        return Trade(
            entry_time=market_state.timestamp,
            entry_price=spot,
            direction='short',
            size=1,
            instrument='SPY',
            strategy='gex_momentum',
            stop_loss=stop,
            take_profit=target
        )

    return None


# =============================================================================
# UTILITY: Strategy Combiner
# =============================================================================

class StrategyEnsemble:
    """
    Combine multiple strategies with allocation weights.

    Allows running multiple strategies simultaneously with position limits.
    """

    def __init__(self, max_total_positions: int = 5):
        self.strategies = []
        self.weights = []
        self.max_positions = max_total_positions

    def add_strategy(self, strategy_func, weight: float = 1.0):
        """Add a strategy with optional weight."""
        self.strategies.append(strategy_func)
        self.weights.append(weight)

    def generate_signals(self, market_state: MarketState,
                         portfolio: Portfolio) -> list:
        """
        Generate signals from all strategies.

        Returns:
            List of Trade objects (may be empty)
        """
        signals = []

        # Check position limit
        if len(portfolio.positions) >= self.max_positions:
            return signals

        for strategy, weight in zip(self.strategies, self.weights):
            try:
                signal = strategy(market_state, portfolio)
                if signal:
                    # Adjust size by weight
                    signal.size = int(signal.size * weight)
                    if signal.size > 0:
                        signals.append(signal)
            except Exception as e:
                print(f"Error in {strategy.__name__}: {e}")

        return signals


# =============================================================================
# STRATEGY DESCRIPTIONS (for documentation)
# =============================================================================

STRATEGY_DESCRIPTIONS = {
    'gamma_flip_breakout': {
        'name': 'Gamma Flip Breakout',
        'type': 'Momentum',
        'timeframe': 'Intraday to Swing',
        'description': 'Trades breakouts through gamma flip level, exploiting regime transition',
        'edge': 'Dealer hedging accelerates move after flip crossover',
        'risk': 'False breakouts when GEX is weak; whipsaws in ranging markets',
        'best_conditions': 'Clear directional move with high GEX magnitude',
    },
    'deep_negative_gamma_reversion': {
        'name': 'Deep Negative Gamma Mean Reversion',
        'type': 'Mean Reversion',
        'timeframe': 'Swing (1-5 days)',
        'description': 'Counter-trend longs in oversold, high-fear environments',
        'edge': 'Overextension in negative gamma creates snapback opportunity',
        'risk': 'Catching falling knives; requires strict risk management',
        'best_conditions': 'IV rank >60, price >2% below flip, high vol premium',
    },
    'positive_gamma_range_fade': {
        'name': 'Positive Gamma Range Fade',
        'type': 'Mean Reversion',
        'timeframe': 'Intraday',
        'description': 'Fades moves in positive gamma (dealer hedging opposes direction)',
        'edge': 'Dealer flows naturally push price back toward gamma-heavy strikes',
        'risk': 'Strong catalysts can overcome dealer flows',
        'best_conditions': 'Low IV rank, strong positive GEX, range-bound tape',
    },
    'gex_momentum': {
        'name': 'GEX Momentum',
        'type': 'Trend Following',
        'timeframe': 'Swing',
        'description': 'Trend following aligned with dealer flow direction',
        'edge': 'High conviction when GEX and price action agree',
        'risk': 'Late entries in extended moves',
        'best_conditions': 'Strong GEX (>5B or <-5B), clear trend, moderate IV',
    },
    'vol_regime_transition': {
        'name': 'Volatility Regime Transition',
        'type': 'Volatility',
        'timeframe': 'Swing (2-10 days)',
        'description': 'Trades volatility regime changes combined with gamma positioning',
        'edge': 'IV rank extremes signal mean reversion; gamma adds directional bias',
        'risk': 'Vol can stay elevated longer than expected; requires patience',
        'best_conditions': 'IV rank >70 or <25, clear vol premium divergence',
    },
}


if __name__ == "__main__":
    print("Available Gamma Strategies:")
    print("=" * 60)
    for key, desc in STRATEGY_DESCRIPTIONS.items():
        print(f"\n{desc['name']} ({desc['type']})")
        print(f"  {desc['description']}")
        print(f"  Edge: {desc['edge']}")
        print(f"  Risk: {desc['risk']}")
