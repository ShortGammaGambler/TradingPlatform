import pandas as pd
import plotly.graph_objs as go

def _update_layout(fig, title, xaxis_range=None, height=600):
    """Helper to update layout with consistent styling."""
    fig.update_layout(
        title=title,
        xaxis_range=xaxis_range,
        height=height,
        template="plotly_dark", # Use a dark theme to match the app
        title_font_size=24,
        xaxis_title_font_size=16, 
        xaxis_tickfont_size=14, 
        yaxis_tickfont_size=14,
        hoverlabel_font_size=14, 
        legend_font_size=14,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            xanchor='center',
            y=-0.2, 
            x=0.5,
        ),
        margin=dict(l=40, r=40, t=80, b=80),
    )
    return fig

def plotly_gex_strike_bars(gex_strikes, spot_price=None):
    from_strike = None
    to_strike = None
    
    if spot_price:
        from_strike = 0.85 * spot_price
        to_strike = 1.15 * spot_price
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Bar(
            x=gex_strikes['Strikes'],
            y=gex_strikes['Gamma Exposure Calls'],
            base=0,
            marker={'color':'#00cc96'}, # Brighter green
            name='Call exposure',
        )
    )
    
    fig.add_trace(
        go.Bar(
            x=gex_strikes['Strikes'],
            y=gex_strikes['Gamma Exposure Puts'],
            base=0,
            marker={'color':'#ef553b'}, # Brighter red
            name='Put exposure',
        )
    )
    
    # fig.add_trace(
    #     go.Scatter(
    #         x=[spot_price], 
    #         y=[dmin,dmax], 
    #         mode='lines', 
    #         line=dict(color='green', width=2, dash='dash'),
    #         name='2018-03-12',
    #     ),
    # )
    
    if spot_price:
        fig.add_vline(
            x=spot_price,
            line_dash="dash", 
            line_color="white",
            annotation_text='Spot price',
            annotation_font_color="white"
        )
    
    
    
    fig = _update_layout(
        fig, 
        title='Gamma Exposure Per 1% Move',
        xaxis_range=[from_strike, to_strike] if from_strike else None
    )
    fig.update_layout(barmode='overlay')
    
    return fig

def plotly_gex_profile(gex_levels, spot_price=None):
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=gex_levels['Strikes'],
            y=gex_levels['Gamma Exposure'],
            mode='lines',
            line=dict(color='#636efa', width=2),
            name='Total Gamma Exposure',
        )
    )
    
    fig.add_trace(
        go.Scatter(
            x=gex_levels['Strikes'],
            y=gex_levels['Gamma Exposure ExNext Expiry'],
            mode='lines',
            line=dict(width=1, dash='dot'),
            name='Ex-Next Expiry',
            visible='legendonly',
        ),
    )
    
    fig.add_trace(
        go.Scatter(
            x=gex_levels['Strikes'],
            y=gex_levels['Gamma Exposure ExNext Friday'],
            mode='lines',
            line=dict(width=1, dash='dot'),
            name='Ex-Next Friday',
            visible='legendonly',
        ),
    )
    
    if spot_price:
        fig.add_vline(
            x=spot_price,
            line_dash="dash", 
            line_color="white",
            annotation_text='Spot price',
            annotation_position='bottom',
            annotation_font_color="white"
        )
        
    # Find Gamma Flip Point
    try:
        zero_cross_idx = np.where(np.diff(np.sign(gex_levels['Gamma Exposure'])))[0][0]

        neg_gamma = gex_levels['Gamma Exposure'][zero_cross_idx]
        pos_gamma = gex_levels['Gamma Exposure'][zero_cross_idx+1]
        neg_strike = gex_levels['Strikes'][zero_cross_idx]
        pos_strike = gex_levels['Strikes'][zero_cross_idx+1]

        zero_gamma = pos_strike - ((pos_strike - neg_strike) * pos_gamma/(pos_gamma-neg_gamma))
        # zero_gamma = zero_gamma[0]
        
        
        fig.add_vline(
            x=zero_gamma,
            line_dash="solid", 
            line_color="yellow",
            annotation_text=f'Gamma Flip: {zero_gamma:.0f}',
            annotation_position='top',
            annotation_font_color="yellow"
        )
        
        # Add background
        fig.add_vrect(
            x0=gex_levels['Strikes'].min(),
            x1=zero_gamma,
            fillcolor="red",
            opacity=0.1,
            line_width=0,
        )
        fig.add_vrect(
            x0=zero_gamma,
            x1=gex_levels['Strikes'].max(),
            fillcolor="green",
            opacity=0.1,
            line_width=0,
        )
        
        title_text = f'Gamma Exposure Profile (Flip: {zero_gamma:.0f})'
    except (IndexError, KeyError, ValueError):
        title_text = 'Gamma Exposure Profile'
        zero_gamma = None
    
    # Add zero line
    fig.add_hline(
            y=0,
            line_color="gray",
            line_width=1,
        )

    # fig.add_trace(
    #     go.Scatter(
    #         x=[gex_levels['Strikes'].min(), zero_gamma, zero_gamma, gex_levels['Strikes'].min()],
    #         y=[gex_levels['Gamma Exposure'].min(), gex_levels['Gamma Exposure'].min(), gex_levels['Gamma Exposure'].max(), gex_levels['Gamma Exposure'].max()],
    #         fill='tozeroy',
    #         fillcolor='green',
    #         mode='none',
    #         showlegend=False
    #     ),
    # )
    
    
    fig = _update_layout(
        fig, 
        title=title_text,
        xaxis_range=[gex_levels['Strikes'].min(), gex_levels['Strikes'].max()]
    )
    
    return fig

def plotly_candlestick_gex(ohlc, historic_gex=None):
    fig = go.Figure()
    
    # Add candlestick
    fig.add_trace(
        go.Candlestick(
            x=ohlc.index,
            open=ohlc['Open'],
            high=ohlc['High'],
            low=ohlc['Low'],
            close=ohlc['Close'],
            # mode='lines',
            # marker={'color':'green'},
            name='SPX',
        )
    )
    
    # Add lines with historic gex
    if historic_gex is not None and not historic_gex.empty:
        fig.add_trace(
            go.Scatter(
                x=historic_gex.index,
                y=historic_gex['Zero Gamma'],
                mode='lines',
                line=dict(color='orange', width=1.5),
                name='Gamma Flip Level',
                # visible='legendonly',
            ),
        )
    
    # Calculate range for last 60 days if possible
    if len(ohlc) > 60:
        start_range = ohlc.index[-60]
    else:
        start_range = ohlc.index[0]

    fig = _update_layout(
        fig, 
        title='SPX Price Action & Gamma Flip Levels',
        xaxis_range=[start_range, ohlc.index.max()],
        height=650
    )
    
    fig.update_xaxes(
        rangeslider_visible=False,
        showspikes=True,
        spikecolor='gray',
        spikethickness=1,
        spikemode="across",
    )
    
