"""
Trade Journal & Performance Tracker
Track actual trades and analyze performance
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import json
from pathlib import Path


@dataclass
class JournalEntry:
    """Single trade journal entry"""
    entry_id: str
    entry_date: datetime
    exit_date: Optional[datetime]
    symbol: str
    strategy_name: str
    direction: str  # "Bullish", "Bearish", "Neutral"
    
    # Position details
    contracts: int
    entry_price: float
    exit_price: Optional[float]
    strikes: Dict[str, float]
    expiration: str
    dte_entry: int
    dte_exit: Optional[int]
    
    # Market conditions at entry
    market_regime: str
    vix_entry: float
    dix_entry: Optional[float]
    underlying_price_entry: float
   
    underlying_price_exit: Optional[float]
    
    # Performance
    realized_pnl: Optional[float]
    max_profit_potential: float
    max_loss_potential: float
    roi_pct: Optional[float]
    
    # Analysis
    trade_plan: str
    exit_reason: str
    notes: str
    tags: List[str]
    
    # Outcome
    status: str  # "OPEN", "CLOSED_WIN", "CLOSED_LOSS", "CLOSED_BREAK_EVEN"
    
    def to_dict(self):
        """Convert to dictionary for storage"""
        data = asdict(self)
        # Convert datetime to string
        data['entry_date'] = self.entry_date.isoformat()
        data['exit_date'] = self.exit_date.isoformat() if self.exit_date else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict):
        """Create from dictionary"""
        data['entry_date'] = datetime.fromisoformat(data['entry_date'])
        if data['exit_date']:
            data['exit_date'] = datetime.fromisoformat(data['exit_date'])
        return cls(**data)


@dataclass
class PerformanceAnalytics:
    """Performance analytics summary"""
    # Overall metrics
    total_trades: int
    open_trades: int
    closed_trades: int
    winning_trades: int
    losing_trades: int
    break_even_trades: int
    
    # Returns
    total_pnl: float
    total_return_pct: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    
    # Success rates
    win_rate: float
    profit_factor: float
    avg_roi: float
    
    # By strategy
    best_strategy: str
    worst_strategy: str
    strategy_performance: Dict[str, Dict]
    
    # By regime
    best_regime: str
    regime_performance: Dict[str, Dict]
    
    # Streaks
    current_streak: int  # Positive = winning, negative = losing
    longest_win_streak: int
    longest_loss_streak: int
    
    # Timing
    avg_hold_time: float  # days
    best_dte_entry: int
    
    # Psychological
    revenge_trades: int  # Trades after losses
    overtrading_score: float  # 0-100, higher = more overtrading


class TradeJournal:
    """
    Comprehensive trade journal with performance analytics
    """
    
    def __init__(self, storage_path: str = "trade_journal.json"):
        """
        Initialize trade journal
        
        Args:
            storage_path: Path to store journal data
        """
        self.storage_path = Path(storage_path)
        self.entries: List[JournalEntry] = []
        self.load()
    
    def add_entry(self, entry: JournalEntry):
        """Add new trade to journal"""
        self.entries.append(entry)
        self.save()
    
    def update_entry(self, entry_id: str, updates: Dict):
        """Update existing trade"""
        for entry in self.entries:
            if entry.entry_id == entry_id:
                for key, value in updates.items():
                    setattr(entry, key, value)
                
                # Auto-update status if closed
                if entry.exit_date and entry.realized_pnl is not None:
                    if entry.realized_pnl > 0:
                        entry.status = "CLOSED_WIN"
                    elif entry.realized_pnl < 0:
                        entry.status = "CLOSED_LOSS"
                    else:
                        entry.status = "CLOSED_BREAK_EVEN"
                
                self.save()
                break
    
    def get_entry(self, entry_id: str) -> Optional[JournalEntry]:
        """Get specific trade"""
        for entry in self.entries:
            if entry.entry_id == entry_id:
                return entry
        return None
    
    def get_open_trades(self) -> List[JournalEntry]:
        """Get all open trades"""
        return [e for e in self.entries if e.status == "OPEN"]
    
    def get_closed_trades(self) -> List[JournalEntry]:
        """Get all closed trades"""
        return [e for e in self.entries if e.status != "OPEN"]
    
    def analyze_performance(self) -> PerformanceAnalytics:
        """
        Comprehensive performance analysis
        """
        
        closed = self.get_closed_trades()
        
        if not closed:
            return self._empty_analytics()
        
        # Basic counts
        total_trades = len(self.entries)
        open_trades = len([e for e in self.entries if e.status == "OPEN"])
        closed_trades = len(closed)
        
        winning = [e for e in closed if e.status == "CLOSED_WIN"]
        losing = [e for e in closed if e.status == "CLOSED_LOSS"]
        break_even = [e for e in closed if e.status == "CLOSED_BREAK_EVEN"]
        
        # P&L metrics
        total_pnl = sum(e.realized_pnl for e in closed if e.realized_pnl)
        
        avg_win = np.mean([e.realized_pnl for e in winning]) if winning else 0
        avg_loss = np.mean([e.realized_pnl for e in losing]) if losing else 0
        largest_win = max([e.realized_pnl for e in winning]) if winning else 0
        largest_loss = min([e.realized_pnl for e in losing]) if losing else 0
        
        # Success metrics
        win_rate = len(winning) / len(closed) * 100 if closed else 0
        
        gross_profit = sum(e.realized_pnl for e in winning)
        gross_loss = abs(sum(e.realized_pnl for e in losing))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        avg_roi = np.mean([e.roi_pct for e in closed if e.roi_pct]) if closed else 0
        
        # By strategy
        strategy_performance = self._analyze_by_category(closed, 'strategy_name')
        best_strategy = max(strategy_performance.items(), key=lambda x: x[1]['win_rate'])[0] if strategy_performance else "N/A"
        worst_strategy = min(strategy_performance.items(), key=lambda x: x[1]['win_rate'])[0] if strategy_performance else "N/A"
        
        # By regime
        regime_performance = self._analyze_by_category(closed, 'market_regime')
        best_regime = max(regime_performance.items(), key=lambda x: x[1]['win_rate'])[0] if regime_performance else "N/A"
        
        # Streaks
        streaks = self._calculate_streaks(closed)
        
        # Timing
        hold_times = [(e.exit_date - e.entry_date).days for e in closed if e.exit_date]
        avg_hold_time = np.mean(hold_times) if hold_times else 0
        
        dte_entries = [e.dte_entry for e in winning if e.dte_entry]
        best_dte = int(np.median(dte_entries)) if dte_entries else 45
        
        # Psychological
        revenge_trades = self._count_revenge_trades(closed)
        overtrading_score = self._calculate_overtrading_score()
        
        # Total return %
        initial_capital = 100000  # Would track actual capital
        total_return_pct = (total_pnl / initial_capital) * 100
        
        return PerformanceAnalytics(
            total_trades=total_trades,
            open_trades=open_trades,
            closed_trades=closed_trades,
            winning_trades=len(winning),
            losing_trades=len(losing),
            break_even_trades=len(break_even),
            total_pnl=total_pnl,
            total_return_pct=total_return_pct,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_roi=avg_roi,
            best_strategy=best_strategy,
            worst_strategy=worst_strategy,
            strategy_performance=strategy_performance,
            best_regime=best_regime,
            regime_performance=regime_performance,
            current_streak=streaks['current'],
            longest_win_streak=streaks['longest_win'],
            longest_loss_streak=streaks['longest_loss'],
            avg_hold_time=avg_hold_time,
            best_dte_entry=best_dte,
            revenge_trades=revenge_trades,
            overtrading_score=overtrading_score
        )
    
    def _analyze_by_category(
        self,
        trades: List[JournalEntry],
        category: str
    ) -> Dict[str, Dict]:
        """Analyze performance by category (strategy, regime, etc.)"""
        
        categories = {}
        
        for trade in trades:
            cat_value = getattr(trade, category, "Unknown")
            
            if cat_value not in categories:
                categories[cat_value] = {
                    'trades': [],
                    'wins': 0,
                    'losses': 0,
                    'total_pnl': 0,
                    'win_rate': 0
                }
            
            categories[cat_value]['trades'].append(trade)
            if trade.status == "CLOSED_WIN":
                categories[cat_value]['wins'] += 1
            elif trade.status == "CLOSED_LOSS":
                categories[cat_value]['losses'] += 1
            
            if trade.realized_pnl:
                categories[cat_value]['total_pnl'] += trade.realized_pnl
        
        # Calculate win rates
        for cat_value, data in categories.items():
            total = len(data['trades'])
            data['win_rate'] = (data['wins'] / total * 100) if total > 0 else 0
        
        return categories
    
    def _calculate_streaks(self, trades: List[JournalEntry]) -> Dict[str, int]:
        """Calculate winning/losing streaks"""
        
        if not trades:
            return {'current': 0, 'longest_win': 0, 'longest_loss': 0}
        
        # Sort by exit date
        sorted_trades = sorted([t for t in trades if t.exit_date], key=lambda x: x.exit_date)
        
        current_streak = 0
        longest_win = 0
        longest_loss = 0
        temp_streak = 0
        last_was_win = None
        
        for trade in sorted_trades:
            is_win = trade.status == "CLOSED_WIN"
            
            if last_was_win is None:
                # First trade
                temp_streak = 1 if is_win else -1
            elif is_win == last_was_win:
                # Streak continues
                if is_win:
                    temp_streak += 1
                else:
                    temp_streak -= 1
            else:
                # Streak broken
                if last_was_win:
                    longest_win = max(longest_win, temp_streak)
                else:
                    longest_loss = max(longest_loss, abs(temp_streak))
                
                temp_streak = 1 if is_win else -1
            
            last_was_win = is_win
            current_streak = temp_streak
        
        # Check final streak
        if last_was_win:
            longest_win = max(longest_win, temp_streak)
        else:
            longest_loss = max(longest_loss, abs(temp_streak))
        
        return {
            'current': current_streak,
            'longest_win': longest_win,
            'longest_loss': longest_loss
        }
    
    def _count_revenge_trades(self, trades: List[JournalEntry]) -> int:
        """Count trades entered within 24h after a loss"""
        
        if len(trades) < 2:
            return 0
        
        sorted_trades = sorted([t for t in trades if t.entry_date], key=lambda x: x.entry_date)
        
        revenge_count = 0
        
        for i in range(1, len(sorted_trades)):
            prev_trade = sorted_trades[i-1]
            curr_trade = sorted_trades[i]
            
            # Check if previous was a loss
            if prev_trade.status == "CLOSED_LOSS" and prev_trade.exit_date:
                # Check if current trade entered within 24h
                time_diff = (curr_trade.entry_date - prev_trade.exit_date).total_seconds() / 3600
                
                if time_diff < 24:
                    revenge_count += 1
        
        return revenge_count
    
    def _calculate_overtrading_score(self) -> float:
        """Calculate overtrading score (0-100)"""
        
        # Would analyze:
        # - Trades per day
        # - Trades after losses
        # - Deviation from plan
        # - Impulse trades (entered quickly)
        
        # Simplified version
        if len(self.entries) < 10:
            return 0
        
        # Average trades per week
        date_range = (self.entries[-1].entry_date - self.entries[0].entry_date).days
        weeks = max(1, date_range / 7)
        trades_per_week = len(self.entries) / weeks
        
        # Overtrading if > 5 trades/week
        score = min(100, (trades_per_week / 5) * 50)
        
        return score
    
    def _empty_analytics(self) -> PerformanceAnalytics:
        """Return empty analytics"""
        return PerformanceAnalytics(
            total_trades=0, open_trades=0, closed_trades=0,
            winning_trades=0, losing_trades=0, break_even_trades=0,
            total_pnl=0, total_return_pct=0,
            avg_win=0, avg_loss=0, largest_win=0, largest_loss=0,
            win_rate=0, profit_factor=0, avg_roi=0,
            best_strategy="N/A", worst_strategy="N/A",
            strategy_performance={}, best_regime="N/A",
            regime_performance={}, current_streak=0,
            longest_win_streak=0, longest_loss_streak=0,
            avg_hold_time=0, best_dte_entry=45,
            revenge_trades=0, overtrading_score=0
        )
    
    def save(self):
        """Save journal to disk"""
        data = [entry.to_dict() for entry in self.entries]
        
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load(self):
        """Load journal from disk"""
        if not self.storage_path.exists():
            return
        
        with open(self.storage_path, 'r') as f:
            data = json.load(f)
        
        self.entries = [JournalEntry.from_dict(entry) for entry in data]
    
    def export_to_csv(self, filepath: str):
        """Export journal to CSV"""
        if not self.entries:
            return
        
        df = pd.DataFrame([entry.to_dict() for entry in self.entries])
        df.to_csv(filepath, index=False)
    
    def import_from_csv(self, filepath: str):
        """Import trades from CSV"""
        df = pd.read_csv(filepath)
        
        for _, row in df.iterrows():
            entry = JournalEntry.from_dict(row.to_dict())
            self.entries.append(entry)
        
        self.save()


def create_performance_dashboard(analytics: PerformanceAnalytics):
    """Create performance visualization"""
    import plotly.graph_objs as go
    from plotly.subplots import make_subplots
    
    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=(
            'Win Rate', 'P&L Distribution', 'Performance by Strategy',
            'Win Streaks', 'Hold Time Distribution', 'Monthly Returns'
        ),
        specs=[
            [{"type": "indicator"}, {"type": "bar"}, {"type": "bar"}],
            [{"type": "bar"}, {"type": "histogram"}, {"type": "bar"}]
        ]
    )
    
    # 1. Win Rate Gauge
    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=analytics.win_rate,
            title={'text': "Win Rate (%)"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "#00cc96" if analytics.win_rate > 50 else "#ef553b"},
                'steps': [
                    {'range': [0, 40], 'color': '#ef553b'},
                    {'range': [40, 60], 'color': '#ffa500'},
                    {'range': [60, 100], 'color': '#00cc96'}
                ]
            }
        ),
        row=1, col=1
    )
    
    # 2. Win/Loss bar
    fig.add_trace(
        go.Bar(
            x=['Wins', 'Losses'],
            y=[analytics.winning_trades, analytics.losing_trades],
            marker_color=['#00cc96', '#ef553b']
        ),
        row=1, col=2
    )
    
    # 3. Strategy performance
    if analytics.strategy_performance:
        strategies = list(analytics.strategy_performance.keys())[:5]
        win_rates = [analytics.strategy_performance[s]['win_rate'] for s in strategies]
        
        fig.add_trace(
            go.Bar(
                x=strategies,
                y=win_rates,
                marker_color=['#00cc96' if wr > 50 else '#ef553b' for wr in win_rates]
            ),
            row=1, col=3
        )
    
    # 4. Streaks
    fig.add_trace(
        go.Bar(
            x=['Current', 'Longest Win', 'Longest Loss'],
            y=[analytics.current_streak, analytics.longest_win_streak, -analytics.longest_loss_streak],
            marker_color=['#ffa500', '#00cc96', '#ef553b']
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        title_text="Trading Performance Dashboard",
        height=800,
        showlegend=False,
        template='plotly_dark',
        paper_bgcolor='#0e1117',
        plot_bgcolor='#0e1117'
    )
    
    return fig
