"""
Portfolio Tracker & Live P&L Monitor
Real-time position tracking with Greeks and P&L
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path


@dataclass
class Position:
    """Single position in portfolio"""
    position_id: str
    symbol: str
    strategy_name: str
    entry_date: datetime
    
    # Legs (each option in the strategy)
    legs: List[Dict]  # [{type: 'call/put', strike, qty, premium, ...}]
    
    # Current market data
    current_underlying_price: float
    current_iv: float
    
    # Greeks
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    
    # P&L
    entry_cost: float = 0.0
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    # Risk metrics
    max_profit: float = 0.0
    max_loss: float = 0.0
    breakeven_points: List[float] = field(default_factory=list)
    
    # Metadata
    days_in_trade: int = 0
    dte_remaining: int = 0
    status: str = "OPEN"  # OPEN, CLOSED, EXPIRED
    
    def update_greeks(self, greeks: Dict):
        """Update position Greeks"""
        self.delta = greeks.get('delta', 0)
        self.gamma = greeks.get('gamma', 0)
        self.theta = greeks.get('theta', 0)
        self.vega = greeks.get('vega', 0)
    
    def update_pnl(self, current_price: float, current_iv: float):
        """Update P&L based on current market"""
        self.current_underlying_price = current_price
        self.current_iv = current_iv
        
        # Calculate current value (simplified - use Black-Scholes in production)
        self.current_value = self._estimate_current_value()
        self.unrealized_pnl = self.current_value - self.entry_cost
        
        # Update days in trade
        self.days_in_trade = (datetime.now() - self.entry_date).days
    
    def _estimate_current_value(self) -> float:
        """Estimate current position value"""
        # Simplified valuation
        # In production, use proper Black-Scholes pricing
        total_value = 0.0
        
        for leg in self.legs:
            # Calculate intrinsic value
            if leg['type'] == 'call':
                intrinsic = max(0, self.current_underlying_price - leg['strike'])
            else:  # put
                intrinsic = max(0, leg['strike'] - self.current_underlying_price)
            
            # Add time value (simplified)
            time_value = leg['premium'] * (self.dte_remaining / leg.get('initial_dte', 45))
            
            leg_value = (intrinsic + time_value) * leg['qty'] * 100
            total_value += leg_value if leg['action'] == 'buy' else -leg_value
        
        return total_value


@dataclass
class PortfolioMetrics:
    """Portfolio-level metrics"""
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    
    # Greeks
    net_delta: float
    net_gamma: float
    net_theta: float
    net_vega: float
    
    # Risk
    total_buying_power_used: float
    portfolio_margin: float
    max_portfolio_loss: float
    
    # Performance
    win_rate: float
    avg_winner: float
    avg_loser: float
    largest_winner: float
    largest_loser: float
    
    # Diversification
    num_positions: int
    num_symbols: int
    concentration_risk: float  # % in largest position


class PortfolioTracker:
    """
    Track live portfolio with real-time P&L and Greeks
    """
    
    def __init__(self, account_balance: float = 100000, storage_path: str = "portfolio.json"):
        self.account_balance = account_balance
        self.storage_path = Path(storage_path)
        self.positions: List[Position] = []
        self.closed_positions: List[Position] = []
        self.load()
    
    def add_position(self, position: Position):
        """Add new position to portfolio"""
        self.positions.append(position)
        self.save()
    
    def close_position(
        self,
        position_id: str,
        close_price: float,
        close_reason: str = ""
    ):
        """Close a position"""
        for pos in self.positions:
            if pos.position_id == position_id:
                pos.status = "CLOSED"
                pos.realized_pnl = pos.unrealized_pnl
                
                self.closed_positions.append(pos)
                self.positions.remove(pos)
                self.save()
                return True
        return False
    
    def update_all_positions(
        self,
        market_data: Dict[str, Dict]
    ):
        """
        Update all positions with current market data
        
        Args:
            market_data: Dict of {symbol: {price, iv, greeks}}
        """
        for pos in self.positions:
            if pos.symbol in market_data:
                data = market_data[pos.symbol]
                pos.update_pnl(data['price'], data['iv'])
                
                if 'greeks' in data:
                    pos.update_greeks(data['greeks'])
    
    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """Calculate portfolio-level metrics"""
        
        if not self.positions and not self.closed_positions:
            return self._empty_metrics()
        
        # Aggregate Greeks
        net_delta = sum(p.delta for p in self.positions)
        net_gamma = sum(p.gamma for p in self.positions)
        net_theta = sum(p.theta for p in self.positions)
        net_vega = sum(p.vega for p in self.positions)
        
        # P&L
        total_unrealized = sum(p.unrealized_pnl for p in self.positions)
        total_realized = sum(p.realized_pnl for p in self.closed_positions)
        total_pnl = total_unrealized + total_realized
        total_pnl_pct = (total_pnl / self.account_balance) * 100
        
        # Current portfolio value
        total_value = sum(p.current_value for p in self.positions)
        
        # Risk
        max_loss = sum(abs(p.max_loss) for p in self.positions)
        
        # Performance (from closed positions)
        closed = self.closed_positions
        winners = [p for p in closed if p.realized_pnl > 0]
        losers = [p for p in closed if p.realized_pnl < 0]
        
        win_rate = len(winners) / len(closed) * 100 if closed else 0
        avg_winner = np.mean([p.realized_pnl for p in winners]) if winners else 0
        avg_loser = np.mean([p.realized_pnl for p in losers]) if losers else 0
        largest_winner = max([p.realized_pnl for p in winners]) if winners else 0
        largest_loser = min([p.realized_pnl for p in losers]) if losers else 0
        
        # Diversification
        symbols = set(p.symbol for p in self.positions)
        
        # Concentration risk (largest position as % of portfolio)
        if self.positions:
            position_sizes = [abs(p.current_value) for p in self.positions]
            concentration = max(position_sizes) / sum(position_sizes) * 100 if sum(position_sizes) > 0 else 0
        else:
            concentration = 0
        
        return PortfolioMetrics(
            total_value=total_value,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            net_delta=net_delta,
            net_gamma=net_gamma,
            net_theta=net_theta,
            net_vega=net_vega,
            total_buying_power_used=total_value,
            portfolio_margin=self.account_balance - total_value,
            max_portfolio_loss=max_loss,
            win_rate=win_rate,
            avg_winner=avg_winner,
            avg_loser=avg_loser,
            largest_winner=largest_winner,
            largest_loser=largest_loser,
            num_positions=len(self.positions),
            num_symbols=len(symbols),
            concentration_risk=concentration
        )
    
    def get_positions_by_symbol(self, symbol: str) -> List[Position]:
        """Get all positions for a specific symbol"""
        return [p for p in self.positions if p.symbol == symbol]
    
    def get_positions_at_risk(self, threshold_pct: float = -10) -> List[Position]:
        """Get positions with unrealized loss > threshold"""
        return [p for p in self.positions 
                if (p.unrealized_pnl / p.entry_cost * 100) < threshold_pct]
    
    def get_positions_to_manage(self) -> Dict[str, List[Position]]:
        """Categorize positions needing attention"""
        
        categories = {
            'take_profit': [],  # > 50% of max profit
            'stop_loss': [],    # < -100% of max loss
            'expiring_soon': [], # < 7 DTE
            'theta_decay': [],  # High theta positions
        }
        
        for pos in self.positions:
            # Take profit candidates
            if pos.max_profit > 0:
                profit_pct = pos.unrealized_pnl / pos.max_profit
                if profit_pct > 0.5:
                    categories['take_profit'].append(pos)
            
            # Stop loss candidates
            if pos.max_loss < 0:
                loss_pct = pos.unrealized_pnl / pos.max_loss
                if loss_pct > 1.0:
                    categories['stop_loss'].append(pos)
            
            # Expiring soon
            if pos.dte_remaining < 7:
                categories['expiring_soon'].append(pos)
            
            # High theta decay
            if pos.theta < -50:  # Losing >$50/day to theta
                categories['theta_decay'].append(pos)
        
        return categories
    
    def save(self):
        """Save portfolio to disk"""
        data = {
            'account_balance': self.account_balance,
            'positions': [self._position_to_dict(p) for p in self.positions],
            'closed': [self._position_to_dict(p) for p in self.closed_positions]
        }
        
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def load(self):
        """Load portfolio from disk"""
        if not self.storage_path.exists():
            return
        
        with open(self.storage_path, 'r') as f:
            data = json.load(f)
        
        self.account_balance = data.get('account_balance', 100000)
        self.positions = [self._dict_to_position(p) for p in data.get('positions', [])]
        self.closed_positions = [self._dict_to_position(p) for p in data.get('closed', [])]
    
    def _position_to_dict(self, pos: Position) -> Dict:
        """Convert position to dict for storage"""
        return {
            'position_id': pos.position_id,
            'symbol': pos.symbol,
            'strategy_name': pos.strategy_name,
            'entry_date': pos.entry_date.isoformat(),
            'legs': pos.legs,
            'current_underlying_price': pos.current_underlying_price,
            'current_iv': pos.current_iv,
            'delta': pos.delta,
            'gamma': pos.gamma,
            'theta': pos.theta,
            'vega': pos.vega,
            'entry_cost': pos.entry_cost,
            'current_value': pos.current_value,
            'unrealized_pnl': pos.unrealized_pnl,
            'realized_pnl': pos.realized_pnl,
            'max_profit': pos.max_profit,
            'max_loss': pos.max_loss,
            'breakeven_points': pos.breakeven_points,
            'days_in_trade': pos.days_in_trade,
            'dte_remaining': pos.dte_remaining,
            'status': pos.status
        }
    
    def _dict_to_position(self, data: Dict) -> Position:
        """Convert dict to Position"""
        data['entry_date'] = datetime.fromisoformat(data['entry_date'])
        return Position(**data)
    
    def _empty_metrics(self) -> PortfolioMetrics:
        """Return empty metrics"""
        return PortfolioMetrics(
            total_value=0, total_pnl=0, total_pnl_pct=0,
            net_delta=0, net_gamma=0, net_theta=0, net_vega=0,
            total_buying_power_used=0, portfolio_margin=self.account_balance,
            max_portfolio_loss=0, win_rate=0, avg_winner=0,
            avg_loser=0, largest_winner=0, largest_loser=0,
            num_positions=0, num_symbols=0, concentration_risk=0
        )


def create_portfolio_dashboard(metrics: PortfolioMetrics, positions: List[Position]):
    """Create portfolio visualization"""
    import plotly.graph_objs as go
    from plotly.subplots import make_subplots
    
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=(
            'Portfolio P&L',
            'Greeks Exposure',
            'Position Distribution',
            'Win/Loss Analysis',
            'Risk Metrics',
            'Open Positions'
        ),
        specs=[
            [{"type": "indicator"}, {"type": "bar"}],
            [{"type": "pie"}, {"type": "bar"}],
            [{"type": "bar"}, {"type": "scatter"}]
        ]
    )
    
    # 1. P&L Gauge
    fig.add_trace(
        go.Indicator(
            mode="gauge+number+delta",
            value=metrics.total_pnl,
            title={'text': "Total P&L ($)"},
            delta={'reference': 0},
            gauge={
                'axis': {'range': [-10000, 10000]},
                'bar': {'color': "#00cc96" if metrics.total_pnl > 0 else "#ef553b"},
                'steps': [
                    {'range': [-10000, 0], 'color': '#ef553b'},
                    {'range': [0, 10000], 'color': '#00cc96'}
                ]
            }
        ),
        row=1, col=1
    )
    
    # 2. Greeks Bar Chart
    greeks = ['Delta', 'Gamma', 'Theta', 'Vega']
    values = [metrics.net_delta, metrics.net_gamma, metrics.net_theta, metrics.net_vega]
    
    fig.add_trace(
        go.Bar(
            x=greeks,
            y=values,
            marker_color=['#00cc96' if v > 0 else '#ef553b' for v in values]
        ),
        row=1, col=2
    )
    
    # 3. Position Distribution
    if positions:
        symbols = [p.symbol for p in positions]
        from collections import Counter
        symbol_counts = Counter(symbols)
        
        fig.add_trace(
            go.Pie(
                labels=list(symbol_counts.keys()),
                values=list(symbol_counts.values()),
                name='Positions'
            ),
            row=2, col=1
        )
    
    # 4. Win/Loss Bar
    fig.add_trace(
        go.Bar(
            x=['Avg Win', 'Avg Loss'],
            y=[metrics.avg_winner, metrics.avg_loser],
            marker_color=['#00cc96', '#ef553b']
        ),
        row=2, col=2
    )
    
    fig.update_layout(
        title_text="Portfolio Dashboard",
        height=1000,
        showlegend=False,
        template='plotly_dark',
        paper_bgcolor='#0e1117',
        plot_bgcolor='#0e1117'
    )
    
    return fig
