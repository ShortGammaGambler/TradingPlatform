"""
Advanced Options Strategy Backtester
Simulates historical performance of strategies with realistic fills and costs
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from src.core.market_regime import MarketRegimeDetector, MarketEnvironment
from src.core.strategy_engine import StrategyEngine
from src.ui.position_sizing import KellyPositionSizer


class TradeStatus(Enum):
    """Status of a trade"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"


@dataclass
class Trade:
    """Individual trade record"""
    entry_date: datetime
    exit_date: Optional[datetime]
    strategy_name: str
    entry_price: float
    exit_price: float
    strikes: Dict[str, float]
    contracts: int
    max_profit: float
    max_loss: float
    realized_pnl: float
    entry_iv: float
    exit_iv: Optional[float]
    dte_entry: int
    dte_exit: Optional[int]
    status: TradeStatus
    confidence: float
    market_regime: str
    win: bool = False
    
    def __post_init__(self):
        """Calculate if trade was a winner"""
        if self.status == TradeStatus.CLOSED or self.status == TradeStatus.EXPIRED:
            self.win = self.realized_pnl > 0


@dataclass
class BacktestResults:
    """Complete backtest results with metrics"""
    trades: List[Trade]
    equity_curve: pd.DataFrame
    metrics: Dict[str, float]
    trade_log: pd.DataFrame
    
    # Performance metrics
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_win_loss_ratio: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # Time-based metrics
    calmar_ratio: float = 0.0
    recovery_factor: float = 0.0
    
    # Advanced metrics
    expectancy: float = 0.0
    system_quality_number: float = 0.0


class OptionsBacktester:
    """
    Comprehensive backtesting engine for options strategies
    """
    
    def __init__(
        self,
        initial_capital: float = 100000,
        commission_per_contract: float = 0.65,
        slippage_pct: float = 0.02,
        kelly_fraction: float = 0.10,
        max_risk_per_trade: float = 0.02,
    ):
        """
        Initialize backtester
        
        Args:
            initial_capital: Starting account balance
            commission_per_contract: Commission per contract (round trip)
            slippage_pct: Slippage as percentage of trade value
            kelly_fraction: Kelly fraction for position sizing
            max_risk_per_trade: Maximum risk per trade as fraction of account
        """
        self.initial_capital = initial_capital
        self.commission_per_contract = commission_per_contract
        self.slippage_pct = slippage_pct
        self.kelly_fraction = kelly_fraction
        self.max_risk_per_trade = max_risk_per_trade
        
        # Components
        self.regime_detector = MarketRegimeDetector()
        self.strategy_engine = StrategyEngine()
        
        # Track state
        self.current_capital = initial_capital
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict] = []
    
    def run_backtest(
        self,
        ohlc_data: pd.DataFrame,
        gex_data: Optional[Dict] = None,
        zero_gamma_data: Optional[pd.DataFrame] = None,
        vix_data: Optional[pd.DataFrame] = None,
        strategy_filter: Optional[List[str]] = None,
        min_confidence: float = 60.0,
        rebalance_frequency: str = 'weekly',  # 'daily', 'weekly', 'monthly'
    ) -> BacktestResults:
        """
        Run complete backtest simulation
        
        Args:
            ohlc_data: Historical OHLC data with DatetimeIndex
            gex_data: Optional GEX data dictionary
            zero_gamma_data: Optional zero gamma levels
            vix_data: Optional VIX data
            strategy_filter: List of strategy names to test (None = all)
            min_confidence: Minimum confidence to take a trade
            rebalance_frequency: How often to check for new trades
            
        Returns:
            BacktestResults with complete analysis
        """
        
        self.current_capital = self.initial_capital
        self.trades = []
        self.equity_curve = []
        
        # Determine rebalance dates
        rebalance_dates = self._get_rebalance_dates(ohlc_data, rebalance_frequency)
        
        # Iterate through rebalance dates
        for i, current_date in enumerate(rebalance_dates):
            if current_date not in ohlc_data.index:
                continue
            
            # Get historical data up to current date
            historical_data = ohlc_data.loc[:current_date]
            
            if len(historical_data) < 50:
                continue  # Need enough data for regime detection
            
            current_price = ohlc_data.loc[current_date, 'Close']
            
            # Get VIX for this date
            current_vix = 20.0  # Default
            if vix_data is not None and current_date in vix_data.index:
                current_vix = vix_data.loc[current_date, 'Close']
            
            # Detect market environment
            market_env = self.regime_detector.analyze_environment(
                ohlc=historical_data,
                current_price=current_price,
                vix=current_vix
            )
            
            # Get strategy recommendations
            recommendations = self.strategy_engine.recommend_strategies(
                market_env=market_env,
                current_price=current_price,
                num_recommendations=10
            )
            
            # Filter by confidence and strategy names
            filtered_recs = [
                rec for rec in recommendations
                if rec.confidence >= min_confidence
                and (strategy_filter is None or rec.name in strategy_filter)
            ]
            
            # Take top strategy if any qualify
            if filtered_recs:
                top_strategy = filtered_recs[0]
                
                # Position sizing
                kelly_sizer = KellyPositionSizer(
                    account_balance=self.current_capital,
                    kelly_fraction=self.kelly_fraction,
                    max_risk_per_trade=self.max_risk_per_trade
                )
                
                # Estimate P&L for position sizing
                estimated_max_loss = 500  # Simplified
                estimated_max_profit = 300
                
                sizing = kelly_sizer.calculate_strategy_sizing(
                    strategy_name=top_strategy.name,
                    confidence=top_strategy.confidence,
                    max_loss_per_contract=estimated_max_loss,
                    max_profit_per_contract=estimated_max_profit
                )
                
                if sizing.contracts_to_trade > 0:
                    # Simulate trade entry
                    trade = self._enter_trade(
                        entry_date=current_date,
                        strategy=top_strategy,
                        contracts=sizing.contracts_to_trade,
                        entry_price=current_price,
                        entry_iv=current_vix,
                        market_env=market_env
                    )
                    
                    # Simulate trade through expiration
                    self._simulate_trade_exit(
                        trade=trade,
                        ohlc_data=ohlc_data,
                        current_date=current_date
                    )
                    
                    self.trades.append(trade)
                    
                    # Update capital
                    self.current_capital += trade.realized_pnl
            
            # Record equity
            self.equity_curve.append({
                'date': current_date,
                'equity': self.current_capital,
                'market_regime': market_env.regime.value,
                'drawdown': 0.0,  # Will calculate later
            })
        
        # Convert equity curve to DataFrame
        equity_df = pd.DataFrame(self.equity_curve)
        
        if not equity_df.empty:
            # Calculate drawdown
            equity_df['peak'] = equity_df['equity'].cummax()
            equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
        
        # Calculate metrics
        metrics = self._calculate_metrics(equity_df)
        
        # Create trade log
        trade_log = self._create_trade_log()
        
        return BacktestResults(
            trades=self.trades,
            equity_curve=equity_df,
            metrics=metrics,
            trade_log=trade_log,
            **metrics
        )
    
    def _get_rebalance_dates(
        self,
        ohlc_data: pd.DataFrame,
        frequency: str
    ) -> List[datetime]:
        """Get dates to check for new trades"""
        
        if frequency == 'daily':
            return ohlc_data.index.tolist()
        elif frequency == 'weekly':
            # Every Monday (or first trading day of week)
            return ohlc_data.resample('W-MON').first().index.tolist()
        elif frequency == 'monthly':
            # First trading day of month
            return ohlc_data.resample('MS').first().index.tolist()
        else:
            return ohlc_data.index.tolist()
    
    def _enter_trade(
        self,
        entry_date: datetime,
        strategy,
        contracts: int,
        entry_price: float,
        entry_iv: float,
        market_env: MarketEnvironment
    ) -> Trade:
        """Simulate entering a trade"""
        
        # Simplified P&L estimation (in production, use Black-Scholes)
        max_profit_per_contract = 300
        max_loss_per_contract = 500
        
        # Apply commissions
        total_commission = contracts * 4 * self.commission_per_contract  # 4 legs avg
        
        return Trade(
            entry_date=entry_date,
            exit_date=None,
            strategy_name=strategy.name,
            entry_price=entry_price,
            exit_price=0.0,
            strikes=strategy.strikes,
            contracts=contracts,
            max_profit=max_profit_per_contract * contracts - total_commission,
            max_loss=max_loss_per_contract * contracts + total_commission,
            realized_pnl=0.0,
            entry_iv=entry_iv,
            exit_iv=None,
            dte_entry=strategy.expiration_dte,
            dte_exit=None,
            status=TradeStatus.OPEN,
            confidence=strategy.confidence,
            market_regime=market_env.regime.value,
        )
    
    def _simulate_trade_exit(
        self,
        trade: Trade,
        ohlc_data: pd.DataFrame,
        current_date: datetime
    ):
        """Simulate trade through to exit"""
        
        # Exit strategy: Hold until 50% profit or expiration
        days_in_trade = 0
        max_days = trade.dte_entry
        
        exit_date = current_date
        
        for i in range(max_days):
            potential_exit = current_date + timedelta(days=i)
            
            if potential_exit not in ohlc_data.index:
                continue
            
            days_in_trade = i
            exit_date = potential_exit
            
            # Simplified P&L calculation
            # In production, use proper options pricing model
            
            # Simulate theta decay and price movement
            time_value_decay = (i / max_days)
            
            exit_price = ohlc_data.loc[potential_exit, 'Close']
            price_change_pct = (exit_price - trade.entry_price) / trade.entry_price
            
            # Rough P&L estimation
            if 'bull' in trade.strategy_name.lower() or 'call' in trade.strategy_name.lower():
                # Bullish strategies
                pnl_pct = price_change_pct * 2 - (time_value_decay * 0.3)
            elif 'bear' in trade.strategy_name.lower() or 'put' in trade.strategy_name.lower():
                # Bearish strategies
                pnl_pct = -price_change_pct * 2 - (time_value_decay * 0.3)
            else:
                # Neutral strategies (theta positive)
                pnl_pct = time_value_decay * 0.5 - abs(price_change_pct) * 0.5
            
            estimated_pnl = trade.max_profit * pnl_pct
            
            # Exit at 50% max profit
            if estimated_pnl >= trade.max_profit * 0.5:
                trade.realized_pnl = estimated_pnl
                trade.exit_date = potential_exit
                trade.exit_price = exit_price
                trade.dte_exit = max_days - i
                trade.status = TradeStatus.CLOSED
                return
            
            # Stop loss at 100% max loss
            if estimated_pnl <= -abs(trade.max_loss):
                trade.realized_pnl = -abs(trade.max_loss)
                trade.exit_date = potential_exit
                trade.exit_price = exit_price
                trade.dte_exit = max_days - i
                trade.status = TradeStatus.CLOSED
                return
        
        # Hold to expiration
        final_pnl = trade.max_profit * pnl_pct
        final_pnl = max(final_pnl, -abs(trade.max_loss))  # Cap at max loss
        
        trade.realized_pnl = final_pnl
        trade.exit_date = exit_date
        trade.exit_price = ohlc_data.loc[exit_date, 'Close']
        trade.dte_exit = 0
        trade.status = TradeStatus.EXPIRED
    
    def _calculate_metrics(self, equity_df: pd.DataFrame) -> Dict[str, float]:
        """Calculate comprehensive performance metrics"""
        
        if equity_df.empty or len(self.trades) == 0:
            return self._empty_metrics()
        
        # Basic P&L metrics
        total_pnl = sum([t.realized_pnl for t in self.trades])
        total_return = (total_pnl / self.initial_capital) * 100
        
        # Win/Loss metrics
        winners = [t for t in self.trades if t.win]
        losers = [t for t in self.trades if not t.win]
        
        win_rate = len(winners) / len(self.trades) * 100 if self.trades else 0
        
        avg_win = np.mean([t.realized_pnl for t in winners]) if winners else 0
        avg_loss = np.mean([t.realized_pnl for t in losers]) if losers else 0
        
        # Profit factor
        gross_profit = sum([t.realized_pnl for t in winners])
        gross_loss = abs(sum([t.realized_pnl for t in losers]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Expectancy
        expectancy = (win_rate/100 * avg_win) + ((1-win_rate/100) * avg_loss)
        
        # Ratios
        returns = equity_df['equity'].pct_change().dropna()
        
        if len(returns) > 0:
            # Annualized return
            days = (equity_df['date'].iloc[-1] - equity_df['date'].iloc[0]).days
            years = days / 365.25
            annualized_return = ((1 + total_return/100) ** (1/years) - 1) * 100 if years > 0 else 0
            
            # Sharpe ratio (assuming 0% risk-free rate)
            sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
            
            # Sortino ratio (downside deviation)
            downside_returns = returns[returns < 0]
            sortino = returns.mean() / downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 and downside_returns.std() > 0 else 0
        else:
            annualized_return = 0
            sharpe = 0
            sortino = 0
        
        # Drawdown metrics
        max_dd = equity_df['drawdown'].min() if not equity_df.empty else 0
        
        # Calmar ratio
        calmar = annualized_return / abs(max_dd) if max_dd != 0 else 0
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'max_drawdown': max_dd,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_win_loss_ratio': abs(avg_win / avg_loss) if avg_loss != 0 else 0,
            'total_trades': len(self.trades),
            'winning_trades': len(winners),
            'losing_trades': len(losers),
            'calmar_ratio': calmar,
            'expectancy': expectancy,
        }
    
    def _empty_metrics(self) -> Dict[str, float]:
        """Return empty metrics dictionary"""
        return {
            'total_return': 0.0,
            'annualized_return': 0.0,
            'sharpe_ratio': 0.0,
            'sortino_ratio': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'avg_win_loss_ratio': 0.0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'calmar_ratio': 0.0,
            'expectancy': 0.0,
        }
    
    def _create_trade_log(self) -> pd.DataFrame:
        """Create detailed trade log DataFrame"""
        
        if not self.trades:
            return pd.DataFrame()
        
        trade_data = []
        
        for trade in self.trades:
            trade_data.append({
                'Entry Date': trade.entry_date,
                'Exit Date': trade.exit_date,
                'Strategy': trade.strategy_name,
                'Market Regime': trade.market_regime,
                'Contracts': trade.contracts,
                'Entry Price': trade.entry_price,
                'Exit Price': trade.exit_price,
                'Entry IV': trade.entry_iv,
                'Confidence': trade.confidence,
                'DTE Entry': trade.dte_entry,
                'DTE Exit': trade.dte_exit,
                'P&L': trade.realized_pnl,
                'Max Profit': trade.max_profit,
                'Max Loss': trade.max_loss,
                'Status': trade.status.value,
                'Win': trade.win,
            })
        
        return pd.DataFrame(trade_data)


def plot_backtest_results(results: BacktestResults):
    """
    Create comprehensive backtest visualization
    
    Returns plotly figure with equity curve and metrics
    """
    import plotly.graph_objs as go
    from plotly.subplots import make_subplots
    
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=(
            'Equity Curve',
            'Drawdown',
            'Monthly Returns',
            'Win/Loss Distribution',
            'Trade Distribution by Regime',
            'Cumulative P&L by Strategy'
        ),
        specs=[
            [{"colspan": 2}, None],
            [{"type": "bar"}, {"type": "bar"}],
            [{"type": "pie"}, {"type": "bar"}],
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.15
    )
    
    # 1. Equity curve
    fig.add_trace(
        go.Scatter(
            x=results.equity_curve['date'],
            y=results.equity_curve['equity'],
            name='Equity',
            line=dict(color='#00cc96', width=2)
        ),
        row=1, col=1
    )
    
    # 2. Drawdown
    fig.add_trace(
        go.Scatter(
            x=results.equity_curve['date'],
            y=results.equity_curve['drawdown'],
            name='Drawdown',
            fill='tozeroy',
            line=dict(color='#ef553b', width=1)
        ),
        row=2, col=1
    )
    
    # 3. Win/Loss distribution
    winners = [t.realized_pnl for t in results.trades if t.win]
    losers = [t.realized_pnl for t in results.trades if not t.win]
    
    fig.add_trace(
        go.Histogram(
            x=winners,
            name='Wins',
            marker_color='#00cc96',
            opacity=0.7
        ),
        row=2, col=2
    )
    
    fig.add_trace(
        go.Histogram(
            x=losers,
            name='Losses',
            marker_color='#ef553b',
            opacity=0.7
        ),
        row=2, col=2
    )
    
    # 4. Regime distribution
    regime_counts = results.trade_log['Market Regime'].value_counts()
    
    fig.add_trace(
        go.Pie(
            labels=regime_counts.index,
            values=regime_counts.values,
            name='Regime Distribution'
        ),
        row=3, col=1
    )
    
    # 5. Strategy P&L
    strategy_pnl = results.trade_log.groupby('Strategy')['P&L'].sum().sort_values()
    
    fig.add_trace(
        go.Bar(
            x=strategy_pnl.values,
            y=strategy_pnl.index,
            orientation='h',
            marker_color=['#00cc96' if x > 0 else '#ef553b' for x in strategy_pnl.values]
        ),
        row=3, col=2
    )
    
    fig.update_layout(
        title_text="Backtest Results Dashboard",
        height=1200,
        showlegend=True,
        template='plotly_dark',
        paper_bgcolor='#0e1117',
        plot_bgcolor='#0e1117',
    )
    
    return fig
