"""
Gamma Strategy Backtesting Engine
Core engine for backtesting gamma-based trading strategies.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

from src.analytics.risk_manager import RiskManager, PositionGreeks, RiskLevel, PortfolioRisk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GammaRegime(Enum):
    """Market gamma regime classification."""
    DEEP_NEGATIVE = "deep_negative"  # High volatility amplification risk
    NEGATIVE = "negative"            # Moderate amplification
    NEUTRAL = "neutral"              # Near gamma flip
    POSITIVE = "positive"            # Dealer hedging stabilizes
    DEEP_POSITIVE = "deep_positive"  # Strong stabilization


@dataclass
class MarketState:
    """Snapshot of market conditions at a point in time."""
    timestamp: datetime
    spot_price: float
    gamma_flip_level: float
    total_gex: float  # Total gamma exposure in $billions
    put_gex: float
    call_gex: float
    iv_rank: float    # 0-100 percentile
    realized_vol: float
    implied_vol: float
    regime: GammaRegime

    @property
    def distance_to_flip(self) -> float:
        """Percentage distance from spot to gamma flip."""
        return (self.spot_price - self.gamma_flip_level) / self.gamma_flip_level * 100

    @property
    def vol_premium(self) -> float:
        """IV minus RV - positive means options are 'expensive'."""
        return self.implied_vol - self.realized_vol


@dataclass
class Trade:
    """Represents a single trade."""
    entry_time: datetime
    entry_price: float
    direction: str  # 'long' or 'short'
    size: float     # Number of contracts or shares
    instrument: str # 'ES', 'SPY', 'SPX_call_4500', etc.
    strategy: str   # Which strategy generated this trade
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None

    @property
    def pnl(self) -> Optional[float]:
        """Calculate P&L if trade is closed."""
        if self.exit_price is None:
            return None
        multiplier = 1 if self.direction == 'long' else -1
        return (self.exit_price - self.entry_price) * multiplier * self.size

    @property
    def pnl_percent(self) -> Optional[float]:
        """P&L as percentage of entry price."""
        if self.pnl is None:
            return None
        return self.pnl / (self.entry_price * self.size) * 100


@dataclass
class Portfolio:
    """Track portfolio state and positions with Greeks."""
    initial_capital: float
    current_capital: float
    positions: List[Trade] = field(default_factory=list)
    closed_trades: List[Trade] = field(default_factory=list)
    max_position_size: float = 0.05  # 5% of capital per position
    max_total_exposure: float = 0.20  # 20% max total exposure

    # Greeks tracking
    net_delta: float = 0.0
    net_gamma: float = 0.0
    net_vega: float = 0.0
    net_theta: float = 0.0

    def can_open_position(self, notional_value: float) -> bool:
        """Check if we can open a new position within risk limits."""
        current_exposure = sum(
            t.entry_price * t.size for t in self.positions
        )
        position_size_ok = notional_value <= self.current_capital * self.max_position_size
        total_exposure_ok = (current_exposure + notional_value) <= self.initial_capital * self.max_total_exposure
        return position_size_ok and total_exposure_ok

    def open_position(self, trade: Trade) -> bool:
        """Open a new position."""
        notional = trade.entry_price * trade.size
        if self.can_open_position(notional):
            self.positions.append(trade)
            return True
        return False

    def close_position(self, trade: Trade, exit_price: float,
                       exit_time: datetime, reason: str) -> float:
        """Close a position and return P&L."""
        trade.exit_price = exit_price
        trade.exit_time = exit_time
        trade.exit_reason = reason
        pnl = trade.pnl or 0
        self.current_capital += pnl
        self.positions.remove(trade)
        self.closed_trades.append(trade)
        return pnl


class BacktestEngine:
    """
    Core backtesting engine for gamma-based strategies.

    Usage:
        engine = BacktestEngine(initial_capital=100000)
        engine.load_data(price_data, gamma_data)
        engine.add_strategy(my_gamma_strategy)
        results = engine.run()

    With risk management:
        rm = RiskManager(account_value=100000)
        engine = BacktestEngine(initial_capital=100000, risk_manager=rm, enable_risk_checks=True)
    """

    def __init__(self, initial_capital: float = 100000,
                 risk_manager: RiskManager = None,
                 enable_risk_checks: bool = True,
                 slippage_bps: float = 5.0,
                 commission_per_contract: float = 0.65):
        """
        Initialize the backtest engine.

        Args:
            initial_capital: Starting capital
            risk_manager: Optional RiskManager instance for Greeks limits
            enable_risk_checks: Whether to validate trades against risk limits
            slippage_bps: Slippage in basis points (default 5 = 0.05%)
            commission_per_contract: Commission per contract traded
        """
        self.portfolio = Portfolio(
            initial_capital=initial_capital,
            current_capital=initial_capital
        )
        self.strategies: List[Callable] = []
        self.price_data: Optional[pd.DataFrame] = None
        self.gamma_data: Optional[pd.DataFrame] = None
        self.results: Dict = {}
        self.equity_curve: List[float] = []

        # Risk management integration
        self.risk_manager = risk_manager or RiskManager(account_value=initial_capital)
        self.enable_risk_checks = enable_risk_checks
        self.slippage_bps = slippage_bps
        self.commission_per_contract = commission_per_contract
        self.transaction_costs = 0.0
        self.rejected_trades: List[Tuple[Trade, str]] = []  # Track rejected trades
        self.delta_history: List[float] = []  # Track delta over time

    def load_data(self, price_data: pd.DataFrame, gamma_data: pd.DataFrame):
        """
        Load price and gamma data for backtesting.

        price_data should have columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        gamma_data should have columns: ['timestamp', 'gamma_flip', 'total_gex', 'put_gex',
                                         'call_gex', 'iv_rank', 'implied_vol', 'realized_vol']
        """
        self.price_data = price_data.set_index('timestamp').sort_index()
        self.gamma_data = gamma_data.set_index('timestamp').sort_index()
        logger.info(f"Loaded {len(self.price_data)} price bars and {len(self.gamma_data)} gamma snapshots")

    def add_strategy(self, strategy_func: Callable):
        """
        Add a strategy function to the backtest.

        Strategy function signature:
            def strategy(market_state: MarketState, portfolio: Portfolio) -> Optional[Trade]
        """
        self.strategies.append(strategy_func)
        logger.info(f"Added strategy: {strategy_func.__name__}")

    def _classify_regime(self, spot: float, flip: float, gex: float) -> GammaRegime:
        """Classify current gamma regime."""
        distance_pct = (spot - flip) / flip * 100

        if distance_pct < -2 and gex < -5:
            return GammaRegime.DEEP_NEGATIVE
        elif distance_pct < 0:
            return GammaRegime.NEGATIVE
        elif abs(distance_pct) < 0.5:
            return GammaRegime.NEUTRAL
        elif distance_pct > 2 and gex > 5:
            return GammaRegime.DEEP_POSITIVE
        else:
            return GammaRegime.POSITIVE

    def _validate_trade_risk(self, trade: Trade, market_state: MarketState) -> Tuple[bool, str]:
        """
        Validate trade against risk limits before execution.

        Checks portfolio Greeks limits to prevent excessive exposure.

        Args:
            trade: Proposed trade
            market_state: Current market conditions

        Returns:
            Tuple of (is_valid, rejection_reason)
        """
        if not self.enable_risk_checks:
            return True, ""

        # Estimate Greeks for new position
        # For underlying/futures: delta = size * direction
        # For options: would need actual Greeks from chain (simplified here)
        direction_mult = 1 if trade.direction == 'long' else -1
        estimated_delta = trade.size * direction_mult

        # Simplified Greeks estimation for options (adjust based on instrument type)
        is_option = any(x in trade.instrument.lower() for x in ['call', 'put', '_c_', '_p_'])
        if is_option:
            # Options have gamma and vega exposure
            estimated_gamma = trade.size * 0.01 * direction_mult
            estimated_vega = trade.size * 0.5 * direction_mult
            estimated_theta = -trade.size * 0.02  # Theta is always negative for long options
        else:
            estimated_gamma = 0
            estimated_vega = 0
            estimated_theta = 0

        # Get current portfolio Greeks
        current_greeks = self.risk_manager.calculate_portfolio_greeks()

        # Check if adding this trade would breach limits
        new_delta = current_greeks['net_delta'] + estimated_delta
        new_gamma = current_greeks['net_gamma'] + estimated_gamma
        new_vega = current_greeks['net_vega'] + estimated_vega
        new_theta = current_greeks['net_theta'] + estimated_theta

        # Validate against limits
        if abs(new_delta) > self.risk_manager.max_delta:
            return False, f"Delta limit breach: {new_delta:.0f} > {self.risk_manager.max_delta:.0f}"

        if abs(new_gamma) > self.risk_manager.max_gamma:
            return False, f"Gamma limit breach: {new_gamma:.4f} > {self.risk_manager.max_gamma:.4f}"

        if abs(new_vega) > self.risk_manager.max_vega:
            return False, f"Vega limit breach: {new_vega:.0f} > {self.risk_manager.max_vega:.0f}"

        if new_theta < self.risk_manager.max_theta:
            return False, f"Theta limit breach: {new_theta:.2f} < {self.risk_manager.max_theta:.2f}"

        return True, ""

    def _calculate_risk_adjusted_size(self, trade: Trade, market_state: MarketState) -> int:
        """
        Calculate position size using RiskManager's sizing methods.

        Uses volatility-adjusted sizing when IV data available,
        falls back to fixed fractional sizing otherwise.

        Args:
            trade: Proposed trade (size will be adjusted)
            market_state: Current market conditions

        Returns:
            Risk-adjusted position size (minimum 1)
        """
        entry_price = trade.entry_price
        stop_loss = trade.stop_loss or entry_price * (0.98 if trade.direction == 'long' else 1.02)

        # Use volatility-adjusted sizing if IV data available
        if market_state.realized_vol > 0:
            # Estimate daily ATR from annualized vol
            # ATR ≈ Price * (Vol / sqrt(252))
            atr_estimate = entry_price * (market_state.realized_vol / 100 / 16)
            size = self.risk_manager.calculate_position_size_volatility_adjusted(
                entry_price=entry_price,
                atr=atr_estimate,
                atr_multiplier=2.0
            )
        else:
            # Fall back to fixed fractional
            size = self.risk_manager.calculate_position_size_fixed_fractional(
                entry_price=entry_price,
                stop_loss=stop_loss
            )

        return max(1, size)  # Minimum 1 contract

    def _apply_slippage_and_costs(self, price: float, direction: str, size: int) -> Tuple[float, float]:
        """
        Apply slippage and calculate transaction costs.

        Slippage models adverse fill prices relative to signal price.

        Args:
            price: Target entry/exit price
            direction: 'long' or 'short'
            size: Number of contracts

        Returns:
            Tuple of (adjusted_price, transaction_cost)
        """
        # Slippage: buys fill higher, sells fill lower
        if direction == 'long':
            slippage_multiplier = 1 + (self.slippage_bps / 10000)
        else:
            slippage_multiplier = 1 - (self.slippage_bps / 10000)

        adjusted_price = price * slippage_multiplier

        # Commission (both entry and exit)
        commission = self.commission_per_contract * size

        return adjusted_price, commission

    def _build_market_state(self, timestamp: datetime) -> Optional[MarketState]:
        """Build market state from available data."""
        try:
            price_row = self.price_data.loc[timestamp]
            gamma_row = self.gamma_data.loc[timestamp]

            spot = price_row['close']
            flip = gamma_row['gamma_flip']
            gex = gamma_row['total_gex']

            return MarketState(
                timestamp=timestamp,
                spot_price=spot,
                gamma_flip_level=flip,
                total_gex=gex,
                put_gex=gamma_row['put_gex'],
                call_gex=gamma_row['call_gex'],
                iv_rank=gamma_row['iv_rank'],
                realized_vol=gamma_row['realized_vol'],
                implied_vol=gamma_row['implied_vol'],
                regime=self._classify_regime(spot, flip, gex)
            )
        except KeyError:
            return None

    def _check_stops(self, timestamp: datetime, current_price: float):
        """Check and execute stops/targets for open positions."""
        for trade in self.portfolio.positions.copy():
            exit_price = None
            exit_reason = None

            # Check stop loss
            if trade.stop_loss:
                if trade.direction == 'long' and current_price <= trade.stop_loss:
                    exit_price = trade.stop_loss
                    exit_reason = 'stop_loss'
                elif trade.direction == 'short' and current_price >= trade.stop_loss:
                    exit_price = trade.stop_loss
                    exit_reason = 'stop_loss'

            # Check take profit (only if not already stopped out)
            if exit_price is None and trade.take_profit:
                if trade.direction == 'long' and current_price >= trade.take_profit:
                    exit_price = trade.take_profit
                    exit_reason = 'take_profit'
                elif trade.direction == 'short' and current_price <= trade.take_profit:
                    exit_price = trade.take_profit
                    exit_reason = 'take_profit'

            # Execute exit if triggered
            if exit_price is not None:
                # Apply exit slippage and costs
                exit_direction = 'short' if trade.direction == 'long' else 'long'
                adjusted_exit, commission = self._apply_slippage_and_costs(exit_price, exit_direction, trade.size)
                self.transaction_costs += commission

                self.portfolio.close_position(trade, adjusted_exit, timestamp, exit_reason)
                self.risk_manager.remove_position(trade.instrument)
                logger.info(f"{exit_reason.replace('_', ' ').title()} hit on {trade.instrument} @ {adjusted_exit:.2f}")

    def run(self) -> Dict:
        """
        Execute the backtest with integrated risk management.

        Returns:
            Dict with performance metrics and trade log
        """
        if self.price_data is None or self.gamma_data is None:
            raise ValueError("Must load data before running backtest")

        if not self.strategies:
            raise ValueError("Must add at least one strategy")

        logger.info("Starting backtest...")
        if self.enable_risk_checks:
            logger.info("Risk checks ENABLED - trades will be validated against Greeks limits")

        # Get common timestamps
        common_times = self.price_data.index.intersection(self.gamma_data.index)
        logger.info(f"Processing {len(common_times)} bars")

        for timestamp in common_times:
            current_price = self.price_data.loc[timestamp, 'close']

            # Check stops first
            self._check_stops(timestamp, current_price)

            # Build market state
            market_state = self._build_market_state(timestamp)
            if market_state is None:
                continue

            # Run each strategy
            for strategy in self.strategies:
                signal = strategy(market_state, self.portfolio)
                if signal is not None:
                    # RISK CHECK: Validate trade against Greeks limits
                    is_valid, reason = self._validate_trade_risk(signal, market_state)
                    if not is_valid:
                        logger.info(f"Trade REJECTED ({strategy.__name__}): {reason}")
                        self.rejected_trades.append((signal, reason))
                        continue

                    # POSITION SIZING: Use risk-adjusted sizing
                    original_size = signal.size
                    signal.size = self._calculate_risk_adjusted_size(signal, market_state)
                    if signal.size != original_size:
                        logger.debug(f"Size adjusted: {original_size} -> {signal.size}")

                    # SLIPPAGE: Apply realistic fill price
                    adjusted_price, commission = self._apply_slippage_and_costs(
                        signal.entry_price, signal.direction, signal.size
                    )
                    signal.entry_price = adjusted_price
                    self.transaction_costs += commission

                    # Open position
                    if self.portfolio.open_position(signal):
                        # Register with risk manager for Greeks tracking
                        direction_mult = 1 if signal.direction == 'long' else -1
                        self.risk_manager.add_position(PositionGreeks(
                            symbol=signal.instrument,
                            delta=signal.size * direction_mult,
                            gamma=signal.size * 0.01 * direction_mult if 'option' in signal.instrument.lower() else 0,
                            theta=-signal.size * 0.02 if 'option' in signal.instrument.lower() else 0,
                            vega=signal.size * 0.5 * direction_mult if 'option' in signal.instrument.lower() else 0,
                            notional=signal.entry_price * signal.size,
                            contracts=signal.size
                        ))
                        logger.info(f"Opened {signal.direction} {signal.size}x {signal.instrument} @ {signal.entry_price:.2f}")

            # Record equity
            open_pnl = sum(
                (current_price - t.entry_price) * (1 if t.direction == 'long' else -1) * t.size
                for t in self.portfolio.positions
            )
            self.equity_curve.append(self.portfolio.current_capital + open_pnl)

            # Track portfolio delta over time
            greeks = self.risk_manager.calculate_portfolio_greeks()
            self.delta_history.append(greeks['net_delta'])

        # Close any remaining positions at last price (with slippage)
        last_price = self.price_data.iloc[-1]['close']
        last_time = self.price_data.index[-1]
        for trade in self.portfolio.positions.copy():
            # Apply exit slippage (opposite direction)
            exit_direction = 'short' if trade.direction == 'long' else 'long'
            exit_price, commission = self._apply_slippage_and_costs(last_price, exit_direction, trade.size)
            self.transaction_costs += commission

            self.portfolio.close_position(trade, exit_price, last_time, 'end_of_backtest')
            self.risk_manager.remove_position(trade.instrument)

        # Calculate metrics
        self.results = self._calculate_metrics()
        return self.results

    def _calculate_metrics(self) -> Dict:
        """Calculate performance metrics including risk-adjusted returns."""
        equity = np.array(self.equity_curve)
        returns = np.diff(equity) / equity[:-1] if len(equity) > 1 else np.array([0])

        total_return = (equity[-1] - equity[0]) / equity[0] * 100 if len(equity) > 0 else 0

        # Sharpe (assuming 252 trading days)
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = np.sqrt(252) * np.mean(returns) / np.std(returns)
        else:
            sharpe = 0

        # Max drawdown
        peak = np.maximum.accumulate(equity) if len(equity) > 0 else np.array([0])
        drawdown = (peak - equity) / peak if np.any(peak > 0) else np.array([0])
        max_dd = np.max(drawdown) * 100 if len(drawdown) > 0 else 0

        # Win rate
        winning_trades = [t for t in self.portfolio.closed_trades if (t.pnl or 0) > 0]
        total_trades = len(self.portfolio.closed_trades)
        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0

        # Profit factor
        gross_profit = sum((t.pnl or 0) for t in self.portfolio.closed_trades if (t.pnl or 0) > 0)
        gross_loss = abs(sum((t.pnl or 0) for t in self.portfolio.closed_trades if (t.pnl or 0) < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # Net return after costs
        initial_capital = equity[0] if len(equity) > 0 else self.portfolio.initial_capital
        net_return_pct = total_return - (self.transaction_costs / initial_capital * 100)

        # Risk metrics
        risk_assessment = self.risk_manager.assess_portfolio_risk()
        max_delta_used = max(abs(d) for d in self.delta_history) if self.delta_history else 0

        # Sortino ratio (downside deviation only)
        negative_returns = returns[returns < 0] if len(returns) > 0 else np.array([0])
        downside_std = np.std(negative_returns) if len(negative_returns) > 1 else 0
        sortino = np.sqrt(252) * np.mean(returns) / downside_std if downside_std > 0 else 0

        return {
            'total_return_pct': round(total_return, 2),
            'net_return_pct': round(net_return_pct, 2),
            'sharpe_ratio': round(sharpe, 2),
            'sortino_ratio': round(sortino, 2),
            'max_drawdown_pct': round(max_dd, 2),
            'total_trades': total_trades,
            'rejected_trades': len(self.rejected_trades),
            'win_rate_pct': round(win_rate, 2),
            'profit_factor': round(profit_factor, 2),
            'final_capital': round(self.portfolio.current_capital, 2),
            'gross_profit': round(gross_profit, 2),
            'gross_loss': round(gross_loss, 2),
            'transaction_costs': round(self.transaction_costs, 2),
            'max_delta_used': round(max_delta_used, 0),
            'final_risk_level': risk_assessment.risk_level.value,
            'risk_warnings': risk_assessment.warnings,
        }


# Example strategy implementation
def gamma_flip_mean_reversion(market_state: MarketState, portfolio: Portfolio) -> Optional[Trade]:
    """
    Strategy: Mean reversion when price extends beyond gamma flip.

    Logic:
    - When price is >1.5% below gamma flip in negative gamma, expect snapback
    - When price is >1.5% above gamma flip in positive gamma, expect pullback
    - Only trade when IV rank is elevated (>50) for premium collection edge
    """
    distance = market_state.distance_to_flip

    # Long signal: Extended below flip, negative gamma, high IV
    if (distance < -1.5 and
        market_state.regime in [GammaRegime.NEGATIVE, GammaRegime.DEEP_NEGATIVE] and
        market_state.iv_rank > 50):

        # Calculate position size (simplified)
        size = 1  # 1 contract/share
        stop = market_state.spot_price * 0.98  # 2% stop
        target = market_state.gamma_flip_level  # Target the flip

        return Trade(
            entry_time=market_state.timestamp,
            entry_price=market_state.spot_price,
            direction='long',
            size=size,
            instrument='SPY',
            strategy='gamma_flip_mean_reversion',
            stop_loss=stop,
            take_profit=target
        )

    return None


if __name__ == "__main__":
    # Demo usage with synthetic data
    print("Gamma Backtest Engine initialized.")
    print("Load your price and gamma data, add strategies, and call run().")
