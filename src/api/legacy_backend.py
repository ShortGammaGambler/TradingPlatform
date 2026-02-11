"""
Trading Terminal Backend - Flask + yfinance
Provides real-time quotes, options chains, IV surface, and term structure data.

Usage:
    pip install -r requirements.txt
    python trading-terminal-backend.py

The frontend will auto-detect this backend at http://localhost:5000.
"""

from flask import Flask, jsonify
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, timedelta
import math
import traceback

app = Flask(__name__)
CORS(app)

# Ticker mapping: frontend ticker -> yfinance ticker
TICKER_MAP = {
    'SPY': 'SPY',
    'SPX': '^GSPC',
    'QQQ': 'QQQ',
    'IWM': 'IWM',
    'VIX': '^VIX',
    'ES': 'ES=F',
}


def get_yf_ticker(ticker):
    """Map frontend ticker symbol to yfinance symbol."""
    return TICKER_MAP.get(ticker.upper(), ticker.upper())


@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })


@app.route('/api/quote/<ticker>')
def quote(ticker):
    """Get real-time quote for a ticker."""
    try:
        yf_ticker = get_yf_ticker(ticker)
        t = yf.Ticker(yf_ticker)
        info = t.fast_info

        price = getattr(info, 'last_price', None)
        if price is None:
            # Fallback: use latest history
            hist = t.history(period='1d')
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])

        prev_close = getattr(info, 'previous_close', None)
        change = None
        change_pct = None
        if price and prev_close:
            change = price - prev_close
            change_pct = (change / prev_close) * 100

        return jsonify({
            'ticker': ticker,
            'yf_ticker': yf_ticker,
            'price': price,
            'previous_close': prev_close,
            'change': change,
            'change_pct': change_pct,
            'market_cap': getattr(info, 'market_cap', None),
            'timestamp': datetime.now().isoformat(),
            'source': 'yfinance'
        })
    except Exception as e:
        return jsonify({'error': str(e), 'ticker': ticker}), 500


@app.route('/api/options/<ticker>')
def options(ticker):
    """Get full options chain for a ticker."""
    try:
        yf_ticker = get_yf_ticker(ticker)
        t = yf.Ticker(yf_ticker)
        expirations = t.options

        if not expirations:
            return jsonify({
                'ticker': ticker,
                'error': 'No options data available',
                'expirations': []
            })

        # Get first 4 expirations to keep response manageable
        chains = []
        for exp_date in expirations[:4]:
            try:
                chain = t.option_chain(exp_date)
                calls_data = []
                puts_data = []

                for _, row in chain.calls.iterrows():
                    calls_data.append({
                        'strike': float(row['strike']),
                        'lastPrice': float(row['lastPrice']) if not math.isnan(row['lastPrice']) else 0,
                        'bid': float(row['bid']) if not math.isnan(row['bid']) else 0,
                        'ask': float(row['ask']) if not math.isnan(row['ask']) else 0,
                        'volume': int(row['volume']) if not math.isnan(row['volume']) else 0,
                        'openInterest': int(row['openInterest']) if not math.isnan(row['openInterest']) else 0,
                        'impliedVolatility': float(row['impliedVolatility']) if not math.isnan(row['impliedVolatility']) else 0,
                    })

                for _, row in chain.puts.iterrows():
                    puts_data.append({
                        'strike': float(row['strike']),
                        'lastPrice': float(row['lastPrice']) if not math.isnan(row['lastPrice']) else 0,
                        'bid': float(row['bid']) if not math.isnan(row['bid']) else 0,
                        'ask': float(row['ask']) if not math.isnan(row['ask']) else 0,
                        'volume': int(row['volume']) if not math.isnan(row['volume']) else 0,
                        'openInterest': int(row['openInterest']) if not math.isnan(row['openInterest']) else 0,
                        'impliedVolatility': float(row['impliedVolatility']) if not math.isnan(row['impliedVolatility']) else 0,
                    })

                chains.append({
                    'expiration': exp_date,
                    'dte': (datetime.strptime(exp_date, '%Y-%m-%d') - datetime.now()).days,
                    'calls': calls_data,
                    'puts': puts_data
                })
            except Exception:
                continue

        return jsonify({
            'ticker': ticker,
            'expirations': expirations[:8],
            'chains': chains,
            'timestamp': datetime.now().isoformat(),
            'source': 'yfinance'
        })
    except Exception as e:
        return jsonify({'error': str(e), 'ticker': ticker}), 500


@app.route('/api/iv-surface/<ticker>')
def iv_surface(ticker):
    """Get IV surface data from real options chains."""
    try:
        yf_ticker = get_yf_ticker(ticker)
        t = yf.Ticker(yf_ticker)
        expirations = t.options

        if not expirations:
            return jsonify({'ticker': ticker, 'error': 'No options data', 'surface': []})

        # Get current price
        price = None
        try:
            price = t.fast_info.last_price
        except Exception:
            hist = t.history(period='1d')
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])

        if not price:
            return jsonify({'ticker': ticker, 'error': 'Cannot determine spot price', 'surface': []})

        surface = []
        for exp_date in expirations[:6]:
            try:
                dte = (datetime.strptime(exp_date, '%Y-%m-%d') - datetime.now()).days
                if dte <= 0:
                    continue

                chain = t.option_chain(exp_date)

                # Combine calls and puts, filter around the money
                for _, row in chain.calls.iterrows():
                    strike = float(row['strike'])
                    iv = float(row['impliedVolatility']) if not math.isnan(row['impliedVolatility']) else 0
                    moneyness = strike / price
                    if 0.8 <= moneyness <= 1.2 and iv > 0:
                        surface.append({
                            'strike': strike,
                            'moneyness': round(moneyness, 4),
                            'dte': dte,
                            'iv': round(iv, 4),
                            'type': 'call'
                        })

                for _, row in chain.puts.iterrows():
                    strike = float(row['strike'])
                    iv = float(row['impliedVolatility']) if not math.isnan(row['impliedVolatility']) else 0
                    moneyness = strike / price
                    if 0.8 <= moneyness <= 1.2 and iv > 0:
                        surface.append({
                            'strike': strike,
                            'moneyness': round(moneyness, 4),
                            'dte': dte,
                            'iv': round(iv, 4),
                            'type': 'put'
                        })
            except Exception:
                continue

        return jsonify({
            'ticker': ticker,
            'spot': price,
            'surface': surface,
            'timestamp': datetime.now().isoformat(),
            'source': 'yfinance'
        })
    except Exception as e:
        return jsonify({'error': str(e), 'ticker': ticker}), 500


@app.route('/api/term-structure/<ticker>')
def term_structure(ticker):
    """Get ATM IV across expirations (term structure)."""
    try:
        yf_ticker = get_yf_ticker(ticker)
        t = yf.Ticker(yf_ticker)
        expirations = t.options

        if not expirations:
            return jsonify({'ticker': ticker, 'error': 'No options data', 'term_structure': {}})

        # Get current price
        price = None
        try:
            price = t.fast_info.last_price
        except Exception:
            hist = t.history(period='1d')
            if not hist.empty:
                price = float(hist['Close'].iloc[-1])

        if not price:
            return jsonify({'ticker': ticker, 'error': 'Cannot determine spot price', 'term_structure': {}})

        raw_term = []
        for exp_date in expirations[:8]:
            try:
                dte = (datetime.strptime(exp_date, '%Y-%m-%d') - datetime.now()).days
                if dte <= 0:
                    continue

                chain = t.option_chain(exp_date)

                # Find ATM call (closest strike to spot)
                calls = chain.calls
                if calls.empty:
                    continue

                calls_valid = calls[calls['impliedVolatility'].notna() & (calls['impliedVolatility'] > 0)]
                if calls_valid.empty:
                    continue

                atm_idx = (calls_valid['strike'] - price).abs().idxmin()
                atm_iv = float(calls_valid.loc[atm_idx, 'impliedVolatility'])

                raw_term.append({
                    'expiration': exp_date,
                    'dte': dte,
                    'atm_iv': round(atm_iv, 4),
                    'atm_strike': float(calls_valid.loc[atm_idx, 'strike'])
                })
            except Exception:
                continue

        # Map to standard tenors (approximate)
        term_map = {}
        for entry in raw_term:
            dte = entry['dte']
            if dte <= 10 and '1W' not in term_map:
                term_map['1W'] = entry['atm_iv']
            elif 10 < dte <= 20 and '2W' not in term_map:
                term_map['2W'] = entry['atm_iv']
            elif 20 < dte <= 45 and '1M' not in term_map:
                term_map['1M'] = entry['atm_iv']
            elif 45 < dte <= 75 and '2M' not in term_map:
                term_map['2M'] = entry['atm_iv']
            elif 75 < dte <= 120 and '3M' not in term_map:
                term_map['3M'] = entry['atm_iv']
            elif dte > 120 and '6M' not in term_map:
                term_map['6M'] = entry['atm_iv']

        return jsonify({
            'ticker': ticker,
            'spot': price,
            'term_structure': term_map,
            'raw': raw_term,
            'timestamp': datetime.now().isoformat(),
            'source': 'yfinance'
        })
    except Exception as e:
        return jsonify({'error': str(e), 'ticker': ticker}), 500


if __name__ == '__main__':
    print('=' * 60)
    print('  Trading Terminal Backend v1.0')
    print('  Endpoints:')
    print('    GET /api/health')
    print('    GET /api/quote/<ticker>')
    print('    GET /api/options/<ticker>')
    print('    GET /api/iv-surface/<ticker>')
    print('    GET /api/term-structure/<ticker>')
    print('=' * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
