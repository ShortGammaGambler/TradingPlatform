"""
Earnings Calendar Integration
Track earnings dates with historical implied move analysis
"""

import requests
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np


@dataclass
class EarningsEvent:
    """Single earnings event"""
    symbol: str
    company_name: str
    earnings_date: datetime
    report_time: str  # "BMO" (before market open) or "AMC" (after market close)
    
    # Estimates
    eps_estimate: Optional[float] = None
    revenue_estimate: Optional[float] = None
    
    # Implied move
    implied_move_pct: Optional[float] = None
    implied_move_dollars: Optional[float] = None
    
    # Historical moves
    avg_move_1yr: Optional[float] = None
    avg_move_3yr: Optional[float] = None
    
    # Current market data
    current_price: float = 0.0
    current_iv: float = 0.0
    iv_rank: float = 0.0  # 0-100
    
    # Days until earnings
    days_until: int = 0
    
    def __post_init__(self):
        """Calculate days until earnings"""
        if self.earnings_date:
            self.days_until = (self.earnings_date - datetime.now()).days


class EarningsCalendar:
    """
    Track upcoming earnings with implied move analysis
    """
    
    def __init__(self):
        self.events: List[EarningsEvent] = []
    
    def fetch_upcoming_earnings(
        self,
        symbols: List[str] = None,
        next_days: int = 30
    ) -> List[EarningsEvent]:
        """
        Fetch upcoming earnings events
        
        Args:
            symbols: List of symbols to track (None = all major stocks)
            next_days: Look ahead this many days
            
        Returns:
            List of EarningsEvent objects
        """
        
        if symbols is None:
            # Default watchlist of major stocks
            symbols = [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META',
                'TSLA', 'NVDA', 'AMD', 'NFLX', 'DIS',
                'BA', 'JPM', 'GS', 'MS', 'BAC'
            ]
        
        events = []
        
        for symbol in symbols:
            event = self._fetch_earnings_for_symbol(symbol)
            if event and event.days_until <= next_days:
                events.append(event)
        
        # Sort by date
        events.sort(key=lambda x: x.earnings_date)
        
        self.events = events
        return events
    
    def _fetch_earnings_for_symbol(self, symbol: str) -> Optional[EarningsEvent]:
        """
        Fetch earnings data for a single symbol
        
        In production, this would connect to:
        - Polygon.io earnings API
        - Alpha Vantage earnings calendar
        - Financial Modeling Prep API
        - Earnings Whispers
        
        For now, returns sample data
        """
        
        # This is a PLACEHOLDER - Replace with actual API call
        # Example for Polygon.io:
        # url = f"https://api.polygon.io/v2/reference/financials/{symbol}"
        # response = requests.get(url, params={'apiKey': API_KEY})
        
        # Sample data for demonstration
        sample_dates = {
            'AAPL': (datetime.now() + timedelta(days=7), 'AMC', 1.42, 89_000_000_000),
            'MSFT': (datetime.now() + timedelta(days=14), 'AMC', 2.95, 56_000_000_000),
            'GOOGL': (datetime.now() + timedelta(days=21), 'AMC', 1.89, 83_000_000_000),
            'AMZN': (datetime.now() + timedelta(days=28), 'AMC', 0.78, 145_000_000_000),
            'TSLA': (datetime.now() + timedelta(days=10), 'AMC', 0.85, 25_000_000_000),
            'NVDA': (datetime.now() + timedelta(days=15), 'AMC', 5.89, 30_000_000_000),
        }
        
        if symbol not in sample_dates:
            return None
        
        date, time, eps, revenue = sample_dates[symbol]
        
        # Calculate implied move (would come from options data)
        implied_move = self._calculate_implied_move(symbol)
        
        event = EarningsEvent(
            symbol=symbol,
            company_name=self._get_company_name(symbol),
            earnings_date=date,
            report_time=time,
            eps_estimate=eps,
            revenue_estimate=revenue,
            implied_move_pct=implied_move['pct'],
            implied_move_dollars=implied_move['dollars'],
            avg_move_1yr=implied_move['avg_1yr'],
            avg_move_3yr=implied_move['avg_3yr'],
            current_price=implied_move['price'],
            current_iv=implied_move['iv'],
            iv_rank=implied_move['iv_rank']
        )
        
        return event
    
    def _calculate_implied_move(self, symbol: str) -> Dict:
        """
        Calculate implied move from options
        
        Implied Move = ATM Straddle Price / Stock Price
        
        In production, fetch from:
        - Polygon.io options snapshot
        - ORATS implied move data
        - Calculate from ATM straddle
        
        Returns sample data for now
        """
        
        # Sample prices
        sample_prices = {
            'AAPL': 185.0,
            'MSFT': 375.0,
            'GOOGL': 140.0,
            'AMZN': 175.0,
            'TSLA': 240.0,
            'NVDA': 500.0
        }
        
        price = sample_prices.get(symbol, 100.0)
        
        # Typical earnings move is 4-8%
        implied_pct = np.random.uniform(4.0, 8.0)
        implied_dollars = price * (implied_pct / 100)
        
        # Historical moves
        avg_1yr = implied_pct * np.random.uniform(0.8, 1.2)
        avg_3yr = implied_pct * np.random.uniform(0.7, 1.1)
        
        # IV data
        iv = np.random.uniform(30, 60)
        iv_rank = np.random.uniform(40, 80)
        
        return {
            'pct': implied_pct,
            'dollars': implied_dollars,
            'avg_1yr': avg_1yr,
            'avg_3yr': avg_3yr,
            'price': price,
            'iv': iv,
            'iv_rank': iv_rank
        }
    
    def _get_company_name(self, symbol: str) -> str:
        """Get company name for symbol"""
        names = {
            'AAPL': 'Apple Inc.',
            'MSFT': 'Microsoft Corporation',
            'GOOGL': 'Alphabet Inc.',
            'AMZN': 'Amazon.com Inc.',
            'META': 'Meta Platforms Inc.',
            'TSLA': 'Tesla Inc.',
            'NVDA': 'NVIDIA Corporation',
            'AMD': 'Advanced Micro Devices',
            'NFLX': 'Netflix Inc.',
            'DIS': 'The Walt Disney Company',
            'BA': 'The Boeing Company',
            'JPM': 'JPMorgan Chase & Co.',
            'GS': 'The Goldman Sachs Group',
            'MS': 'Morgan Stanley',
            'BAC': 'Bank of America Corp.'
        }
        return names.get(symbol, symbol)
    
    def get_this_week_earnings(self) -> List[EarningsEvent]:
        """Get earnings happening this week"""
        return [e for e in self.events if e.days_until <= 7]
    
    def get_high_iv_earnings(self, min_iv_rank: float = 70) -> List[EarningsEvent]:
        """Get earnings with high IV rank (good for selling premium)"""
        return [e for e in self.events if e.iv_rank >= min_iv_rank]
    
    def get_large_move_expected(self, min_move_pct: float = 6.0) -> List[EarningsEvent]:
        """Get earnings with large expected moves"""
        return [e for e in self.events if e.implied_move_pct and e.implied_move_pct >= min_move_pct]
    
    def get_opportunities(self) -> Dict[str, List[EarningsEvent]]:
        """
        Categorize earnings into trading opportunities
        
        Returns dict of:
        - 'straddle_buys': Low implied vs historical (buy straddles)
        - 'straddle_sells': High implied vs historical (sell straddles)
        - 'high_iv': High IV rank (premium selling)
        - 'this_week': Earnings this week
        """
        
        opportunities = {
            'straddle_buys': [],
            'straddle_sells': [],
            'high_iv': [],
            'this_week': []
        }
        
        for event in self.events:
            # This week
            if event.days_until <= 7:
                opportunities['this_week'].append(event)
            
            # High IV
            if event.iv_rank >= 70:
                opportunities['high_iv'].append(event)
            
            # Implied vs historical
            if event.implied_move_pct and event.avg_1yr:
                ratio = event.implied_move_pct / event.avg_1yr
                
                if ratio < 0.9:
                    # Implied move LESS than historical = buy straddle
                    opportunities['straddle_buys'].append(event)
                elif ratio > 1.1:
                    # Implied move MORE than historical = sell straddle
                    opportunities['straddle_sells'].append(event)
        
        return opportunities
    
    def get_strategy_recommendation(self, event: EarningsEvent) -> Dict:
        """
        Get trading strategy recommendation for an earnings event
        
        Returns:
            Dict with strategy, rationale, and risk
        """
        
        if not event.implied_move_pct or not event.avg_1yr:
            return {
                'strategy': 'No Trade',
                'rationale': 'Insufficient data',
                'risk': 'N/A'
            }
        
        ratio = event.implied_move_pct / event.avg_1yr
        
        # Implied < Historical: Market underpricing the move
        if ratio < 0.85:
            return {
                'strategy': 'Buy Straddle',
                'rationale': f'Implied move ({event.implied_move_pct:.1f}%) significantly less than 1-yr avg ({event.avg_1yr:.1f}%). Market may be underpricing volatility.',
                'risk': 'Medium',
                'confidence': 75,
                'max_loss': f'Straddle premium (~${event.implied_move_dollars:.0f})',
                'max_profit': 'Unlimited',
                'breakeven': f'±{event.implied_move_pct:.1f}%'
            }
        
        # Implied > Historical: Market overpricing the move
        elif ratio > 1.15:
            return {
                'strategy': 'Sell Iron Condor',
                'rationale': f'Implied move ({event.implied_move_pct:.1f}%) significantly more than 1-yr avg ({event.avg_1yr:.1f}%). Market may be overpricing volatility.',
                'risk': 'Medium-High',
                'confidence': 70,
                'max_profit': f'Premium collected (~${event.implied_move_dollars * 0.3:.0f})',
                'max_loss': 'Limited to wing width',
                'breakeven': f'±{event.implied_move_pct * 1.2:.1f}%'
            }
        
        # High IV Rank: Sell premium
        elif event.iv_rank > 75:
            return {
                'strategy': 'Sell Credit Spread',
                'rationale': f'IV Rank very high ({event.iv_rank:.0f}). Good time to sell overpriced premium.',
                'risk': 'Medium',
                'confidence': 65,
                'max_profit': 'Premium collected',
                'max_loss': 'Width of spread',
                'breakeven': f'{event.implied_move_pct:.1f}%'
            }
        
        # Neutral: Minor opportunity
        else:
            return {
                'strategy': 'Consider Calendar Spread',
                'rationale': f'Implied vs historical is neutral (ratio: {ratio:.2f}). Consider selling front-month, buying back-month to capture elevated IV.',
                'risk': 'Low-Medium',
                'confidence': 55,
                'max_profit': 'Premium differential',
                'max_loss': 'Net debit paid',
                'breakeven': 'Variable'
            }


def create_earnings_calendar_viz(events: List[EarningsEvent]):
    """Create earnings calendar visualization"""
    import plotly.graph_objs as go
    from plotly.subplots import make_subplots
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'Upcoming Earnings Timeline',
            'Implied vs Historical Move',
            'IV Rank Distribution',
            'Expected Move Distribution'
        ),
        specs=[
            [{"type": "scatter"}, {"type": "bar"}],
            [{"type": "bar"}, {"type": "histogram"}]
        ]
    )
    
    # 1. Timeline
    if events:
        symbols = [e.symbol for e in events]
        dates = [e.earnings_date for e in events]
        colors = ['#00cc96' if e.report_time == 'AMC' else '#ffa500' for e in events]
        
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=symbols,
                mode='markers+text',
                marker=dict(size=15, color=colors),
                text=[e.report_time for e in events],
                textposition='top center',
                name='Earnings'
            ),
            row=1, col=1
        )
    
    # 2. Implied vs Historical
    valid_events = [e for e in events if e.implied_move_pct and e.avg_1yr]
    if valid_events:
        symbols = [e.symbol for e in valid_events]
        implied = [e.implied_move_pct for e in valid_events]
        historical = [e.avg_1yr for e in valid_events]
        
        fig.add_trace(
            go.Bar(name='Implied', x=symbols, y=implied, marker_color='#00cc96'),
            row=1, col=2
        )
        fig.add_trace(
            go.Bar(name='Historical', x=symbols, y=historical, marker_color='#636efa'),
            row=1, col=2
        )
    
    # 3. IV Rank
    if events:
        symbols = [e.symbol for e in events]
        iv_ranks = [e.iv_rank for e in events]
        colors = ['#00cc96' if iv > 70 else '#ffa500' if iv > 50 else '#ef553b' for iv in iv_ranks]
        
        fig.add_trace(
            go.Bar(x=symbols, y=iv_ranks, marker_color=colors),
            row=2, col=1
        )
    
    # 4. Move distribution
    if valid_events:
        moves = [e.implied_move_pct for e in valid_events]
        
        fig.add_trace(
            go.Histogram(x=moves, nbinsx=10, marker_color='#00cc96'),
            row=2, col=2
        )
    
    fig.update_layout(
        title="Earnings Calendar Analysis",
        height=800,
        showlegend=True,
        template='plotly_dark',
        paper_bgcolor='#0e1117',
        plot_bgcolor='#0e1117'
    )
    
    return fig
