"""
Advanced 2D and 3D Visualizations for Options Trading
Includes P&L surfaces, Greeks heat maps, and IV surfaces
"""

import numpy as np
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from typing import Dict, List, Optional


class OptionsVisualizer:
    """
    Advanced visualizations for options analysis
    """
    
    def __init__(self):
        self.dark_theme = {
            'template': 'plotly_dark',
            'paper_bgcolor': '#0e1117',
            'plot_bgcolor': '#0e1117',
            'font_color': '#fafafa',
        }
    
    def plot_pnl_surface_3d(
        self,
        strategy_name: str,
        strikes: Dict[str, float],
        current_price: float,
        days_range: np.ndarray = None,
        price_range: np.ndarray = None,
        iv: float = 25.0
    ) -> go.Figure:
        """
        Create 3D P&L surface for an options strategy
        
        Shows P&L across price movements and time decay
        """
        
        if days_range is None:
            days_range = np.linspace(0, 45, 20)  # 0 to 45 days
        
        if price_range is None:
            price_range = np.linspace(current_price * 0.85, current_price * 1.15, 50)
        
        # Create meshgrid
        X, Y = np.meshgrid(price_range, days_range)
        Z = np.zeros_like(X)
        
        # Calculate P&L for each point (simplified - would use Black-Scholes in production)
        for i in range(len(days_range)):
            for j in range(len(price_range)):
                Z[i, j] = self._calculate_strategy_pnl(
                    strategy_name,
                    strikes,
                    price_range[j],
                    current_price,
                    days_range[i],
                    iv
                )
        
        # Create 3D surface
        fig = go.Figure(data=[
            go.Surface(
                x=X,
                y=Y,
                z=Z,
                colorscale='RdYlGn',
                colorbar=dict(title="P&L ($)", titleside='right'),
                hovertemplate='Price: $%{x:.2f}<br>Days: %{y:.0f}<br>P&L: $%{z:.2f}<extra></extra>'
            )
        ])
        
        # Add zero plane for reference
        fig.add_trace(
            go.Surface(
                x=X,
                y=Y,
                z=np.zeros_like(Z),
                opacity=0.3,
                colorscale=[[0, 'gray'], [1, 'gray']],
                showscale=False,
                hoverinfo='skip'
            )
        )
        
        fig.update_layout(
            title=f'{strategy_name} - 3D P&L Surface',
            scene=dict(
                xaxis_title='Underlying Price ($)',
                yaxis_title='Days to Expiration',
                zaxis_title='Profit/Loss ($)',
                camera=dict(
                    eye=dict(x=1.5, y=1.5, z=1.3)
                )
            ),
            height=700,
            **self.dark_theme
        )
        
        return fig
    
    def plot_pnl_heatmap_2d(
        self,
        strategy_name: str,
        strikes: Dict[str, float],
        current_price: float,
        days_range: np.ndarray = None,
        price_range: np.ndarray = None,
        iv: float = 25.0
    ) -> go.Figure:
        """
        Create 2D P&L heatmap for an options strategy
        """
        
        if days_range is None:
            days_range = np.linspace(0, 45, 30)
        
        if price_range is None:
            price_range = np.linspace(current_price * 0.85, current_price * 1.15, 50)
        
        # Create P&L matrix
        pnl_matrix = np.zeros((len(days_range), len(price_range)))
        
        for i, days in enumerate(days_range):
            for j, price in enumerate(price_range):
                pnl_matrix[i, j] = self._calculate_strategy_pnl(
                    strategy_name,
                    strikes,
                    price,
                    current_price,
                    days,
                    iv
                )
        
        fig = go.Figure(data=go.Heatmap(
            x=price_range,
            y=days_range,
            z=pnl_matrix,
            colorscale='RdYlGn',
            zmid=0,  # Center color scale at zero
            colorbar=dict(title="P&L ($)"),
            hovertemplate='Price: $%{x:.2f}<br>Days: %{y:.0f}<br>P&L: $%{z:.2f}<extra></extra>'
        ))
        
        # Add current price line
        fig.add_vline(
            x=current_price,
            line_dash="dash",
            line_color="white",
            annotation_text="Current Price",
            annotation_position="top"
        )
        
        fig.update_layout(
            title=f'{strategy_name} - P&L Heatmap',
            xaxis_title='Underlying Price ($)',
            yaxis_title='Days to Expiration',
            height=600,
            **self.dark_theme
        )
        
        return fig
    
    def plot_pnl_profile_at_expiration(
        self,
        strategy_name: str,
        strikes: Dict[str, float],
        current_price: float,
        price_range: np.ndarray = None,
    ) -> go.Figure:
        """
        Classic 2D P&L diagram at expiration
        """
        
        if price_range is None:
            price_range = np.linspace(current_price * 0.80, current_price * 1.20, 100)
        
        # Calculate P&L at expiration (0 days)
        pnl = np.array([
            self._calculate_strategy_pnl(strategy_name, strikes, price, current_price, 0, 25.0)
            for price in price_range
        ])
        
        # Calculate current P&L (e.g., 30 days before expiration)
        pnl_current = np.array([
            self._calculate_strategy_pnl(strategy_name, strikes, price, current_price, 30, 25.0)
            for price in price_range
        ])
        
        fig = go.Figure()
        
        # P&L at expiration
        fig.add_trace(go.Scatter(
            x=price_range,
            y=pnl,
            mode='lines',
            name='At Expiration',
            line=dict(color='#00cc96', width=3),
            hovertemplate='Price: $%{x:.2f}<br>P&L: $%{y:.2f}<extra></extra>'
        ))
        
        # Current P&L
        fig.add_trace(go.Scatter(
            x=price_range,
            y=pnl_current,
            mode='lines',
            name='Current (T-30)',
            line=dict(color='#636efa', width=2, dash='dot'),
            hovertemplate='Price: $%{x:.2f}<br>P&L: $%{y:.2f}<extra></extra>'
        ))
        
        # Zero line
        fig.add_hline(y=0, line_dash="solid", line_color="gray", line_width=1)
        
        # Current price
        fig.add_vline(
            x=current_price,
            line_dash="dash",
            line_color="white",
            annotation_text="Current Price"
        )
        
        # Shade profit zones
        fig.add_hrect(
            y0=0, y1=max(pnl) * 1.1,
            fillcolor="green", opacity=0.1,
            line_width=0,
        )
        fig.add_hrect(
            y0=min(pnl) * 1.1, y1=0,
            fillcolor="red", opacity=0.1,
            line_width=0,
        )
        
        fig.update_layout(
            title=f'{strategy_name} - P&L Profile',
            xaxis_title='Underlying Price ($)',
            yaxis_title='Profit/Loss ($)',
            height=600,
            **self.dark_theme
        )
        
        return fig
    
    def plot_greeks_dashboard(
        self,
        strategy_name: str,
        strikes: Dict[str, float],
        current_price: float,
        price_range: np.ndarray = None,
    ) -> go.Figure:
        """
        Multi-panel Greeks visualization (Delta, Gamma, Theta, Vega)
        """
        
        if price_range is None:
            price_range = np.linspace(current_price * 0.85, current_price * 1.15, 100)
        
        # Calculate Greeks (simplified - would use actual Black-Scholes)
        greeks = self._calculate_greeks_profile(strategy_name, strikes, current_price, price_range)
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Delta Profile', 'Gamma Profile', 'Theta Profile', 'Vega Profile'),
            vertical_spacing=0.12,
            horizontal_spacing=0.10
        )
        
        # Delta
        fig.add_trace(
            go.Scatter(x=price_range, y=greeks['delta'], 
                      name='Delta', line=dict(color='#636efa', width=2)),
            row=1, col=1
        )
        
        # Gamma
        fig.add_trace(
            go.Scatter(x=price_range, y=greeks['gamma'],
                      name='Gamma', line=dict(color='#00cc96', width=2)),
            row=1, col=2
        )
        
        # Theta
        fig.add_trace(
            go.Scatter(x=price_range, y=greeks['theta'],
                      name='Theta', line=dict(color='#ef553b', width=2)),
            row=2, col=1
        )
        
        # Vega
        fig.add_trace(
            go.Scatter(x=price_range, y=greeks['vega'],
                      name='Vega', line=dict(color='#ab63fa', width=2)),
            row=2, col=2
        )
        
        # Add current price lines to all subplots
        for row in [1, 2]:
            for col in [1, 2]:
                fig.add_vline(
                    x=current_price,
                    line_dash="dash",
                    line_color="white",
                    line_width=1,
                    row=row, col=col
                )
        
        fig.update_xaxes(title_text="Price ($)", row=2, col=1)
        fig.update_xaxes(title_text="Price ($)", row=2, col=2)
        fig.update_yaxes(title_text="Delta", row=1, col=1)
        fig.update_yaxes(title_text="Gamma", row=1, col=2)
        fig.update_yaxes(title_text="Theta ($)", row=2, col=1)
        fig.update_yaxes(title_text="Vega ($)", row=2, col=2)
        
        fig.update_layout(
            title_text=f"{strategy_name} - Greeks Dashboard",
            height=800,
            showlegend=False,
            **self.dark_theme
        )
        
        return fig
    
    def plot_iv_surface_3d(
        self,
        iv_surface_df: pd.DataFrame,
        current_price: float
    ) -> go.Figure:
        """
        Plot 3D Implied Volatility Surface
        
        Args:
            iv_surface_df: DataFrame with strikes as index, expirations as columns
            current_price: Current underlying price
        """
        
        # Convert to arrays
        strikes = iv_surface_df.index.values
        expirations = iv_surface_df.columns.values
        
        # Create meshgrid
        X, Y = np.meshgrid(strikes, expirations)
        Z = iv_surface_df.T.values
        
        fig = go.Figure(data=[
            go.Surface(
                x=X,
                y=Y,
                z=Z,
                colorscale='Viridis',
                colorbar=dict(title="IV (%)", titleside='right'),
                hovertemplate='Strike: $%{x:.2f}<br>Expiration: %{y}<br>IV: %{z:.1f}%<extra></extra>'
            )
        ])
        
        fig.update_layout(
            title='Implied Volatility Surface',
            scene=dict(
                xaxis_title='Strike Price ($)',
                yaxis_title='Expiration',
                zaxis_title='Implied Volatility (%)',
                camera=dict(eye=dict(x=1.5, y=1.5, z=1.3))
            ),
            height=700,
            **self.dark_theme
        )
        
        return fig
    
    def plot_volatility_smile(
        self,
        strikes: np.ndarray,
        ivs: np.ndarray,
        current_price: float,
        expiration_label: str = ""
    ) -> go.Figure:
        """
        Plot volatility smile/skew for a specific expiration
        """
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=strikes,
            y=ivs,
            mode='lines+markers',
            name='Implied Volatility',
            line=dict(color='#ab63fa', width=3),
            marker=dict(size=8),
            hovertemplate='Strike: $%{x:.2f}<br>IV: %{y:.1f}%<extra></extra>'
        ))
        
        # ATM line
        fig.add_vline(
            x=current_price,
            line_dash="dash",
            line_color="white",
            annotation_text="ATM"
        )
        
        # Identify put and call wings
        atm_idx = np.argmin(np.abs(strikes - current_price))
        if atm_idx < len(strikes) - 1:
            # Shade put side
            fig.add_vrect(
                x0=strikes[0], x1=current_price,
                fillcolor="red", opacity=0.05,
                annotation_text="Put Wing", annotation_position="top left",
                line_width=0
            )
            # Shade call side
            fig.add_vrect(
                x0=current_price, x1=strikes[-1],
                fillcolor="green", opacity=0.05,
                annotation_text="Call Wing", annotation_position="top right",
                line_width=0
            )
        
        title = f'Volatility Smile - {expiration_label}' if expiration_label else 'Volatility Smile'
        
        fig.update_layout(
            title=title,
            xaxis_title='Strike Price ($)',
            yaxis_title='Implied Volatility (%)',
            height=600,
            **self.dark_theme
        )
        
        return fig
    
    def _calculate_strategy_pnl(
        self,
        strategy_name: str,
        strikes: Dict[str, float],
        price_at_calc: float,
        current_price: float,
        days_to_exp: float,
        iv: float
    ) -> float:
        """
        Calculate P&L for a strategy at given price and time
        
        This is simplified - in production, use Black-Scholes pricing
        """
        
        pnl = 0
        
        # Simplified P&L calculations (linear approximation)
        # In production, use proper option pricing models
        
        if 'bull_call_spread' in strategy_name.lower():
            long_strike = strikes.get('long_call', current_price)
            short_strike = strikes.get('short_call', current_price * 1.05)
            
            max_profit = (short_strike - long_strike) * 100  # Per contract
            max_loss = 500  # Debit paid (example)
            
            if price_at_calc >= short_strike:
                pnl = max_profit
            elif price_at_calc <= long_strike:
                pnl = -max_loss * (1 - days_to_exp / 45)  # Time decay
            else:
                pnl = ((price_at_calc - long_strike) / (short_strike - long_strike)) * max_profit - max_loss
        
        elif 'iron_condor' in strategy_name.lower():
            short_put = strikes.get('short_put', current_price * 0.95)
            short_call = strikes.get('short_call', current_price * 1.05)
            
            max_profit = 300  # Credit received
            max_loss = 200  # Width - credit
            
            if short_put <= price_at_calc <= short_call:
                pnl = max_profit * (1 - days_to_exp / 45)
            else:
                pnl = -max_loss * (1 - days_to_exp / 45)
        
        else:
            # Generic placeholder
            pnl = (price_at_calc - current_price) * 10 - (45 - days_to_exp) * 5
        
        return pnl
    
    def _calculate_greeks_profile(
        self,
        strategy_name: str,
        strikes: Dict[str, float],
        current_price: float,
        price_range: np.ndarray
    ) -> Dict[str, np.ndarray]:
        """
        Calculate Greeks profile across price range
        
        Simplified - in production, use Black-Scholes Greeks
        """
        
        delta = []
        gamma = []
        theta = []
        vega = []
        
        for price in price_range:
            # Simplified Greeks (placeholder)
            # Delta: -1 to 1
            d = np.tanh((price - current_price) / (current_price * 0.05))
            delta.append(d)
            
            # Gamma: bell curve around current price
            g = np.exp(-((price - current_price)**2) / (2 * (current_price * 0.05)**2))
            gamma.append(g * 0.01)
            
            # Theta: roughly constant, negative for long positions
            theta.append(-50 if 'long' in strategy_name.lower() else 30)
            
            # Vega: similar to gamma
            vega.append(g * 100)
        
        return {
            'delta': np.array(delta),
            'gamma': np.array(gamma),
            'theta': np.array(theta),
            'vega': np.array(vega)
        }


def create_risk_metrics_gauge(
    current_value: float,
    max_value: float,
    title: str,
    color_scale: str = "RdYlGn"
) -> go.Figure:
    """
    Create a gauge chart for risk metrics
    """
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=current_value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title, 'font': {'size': 24}},
        gauge={
            'axis': {'range': [None, max_value], 'tickwidth': 1},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, max_value * 0.5], 'color': 'lightgreen'},
                {'range': [max_value * 0.5, max_value * 0.8], 'color': 'yellow'},
                {'range': [max_value * 0.8, max_value], 'color': 'red'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': max_value * 0.9
            }
        }
    ))
    
    fig.update_layout(
        height=300,
        paper_bgcolor='#0e1117',
        plot_bgcolor='#0e1117',
        font={'color': '#fafafa'}
    )
    
    return fig
