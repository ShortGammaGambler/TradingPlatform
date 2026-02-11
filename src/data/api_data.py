"""Functions to retrieve data from an API"""

import os 
import json
import requests
import pandas as pd
from dotenv import load_dotenv
import streamlit as st

# Get env variables
load_dotenv()

headers={'User-agent': 'Mozilla/5.0'}

def _get_api_url(key: str) -> str:
    """Helper to get API URL from env vars."""
    url = os.environ.get(key)
    if not url:
        st.error(f"Environment variable {key} not found.")
        return ""
    return url

def fetch_execution_info() -> pd.DataFrame:
    """Fetch execution information."""
    url = _get_api_url('API_GEX_EX_INF')
    if not url: return pd.DataFrame()
    
    try:
        response = requests.get(url=url, headers=headers, stream=True)
        response.raise_for_status()
        content = response.content.decode("utf-8")
        df = pd.DataFrame(json.loads(content))
        return df
    except Exception as e:
        st.error(f"Error fetching execution info: {e}")
        return pd.DataFrame()

def fetch_zero_gamma() -> pd.DataFrame:
    """Fetch zero gamma data."""
    url = _get_api_url('API_GEX_ZERO')
    if not url: return pd.DataFrame()
    
    try:
        response = requests.get(url=url, headers=headers, stream=True)
        response.raise_for_status()
        content = response.content.decode("utf-8")
        
        df = pd.DataFrame.from_dict(json.loads(content), orient='index')
        df = df.reset_index().drop(columns={'level_0'})
        # Safe transformation
        if 'index' in df.columns:
            df['index'] = df['index'].apply(lambda x: x[0] if isinstance(x, list) and len(x) > 0 else x)
        if 'Zero Gamma' in df.columns:
            df['Zero Gamma'] = df['Zero Gamma'].apply(lambda x: x[0] if isinstance(x, list) and len(x) > 0 else x)
            
        df['index'] = pd.to_datetime(df['index'])
        df.set_index(['index'], inplace=True)
        df.index.name='Date'
        return df
    except Exception as e:
        st.error(f"Error fetching zero gamma: {e}")
        return pd.DataFrame()

def fetch_gex_profile() -> dict:
    """Fetch GEX profile data."""
    url = _get_api_url('API_GEX_PROFILE')
    if not url: return {}
    
    try:
        response = requests.get(url=url, headers=headers, stream=True)
        response.raise_for_status()
        content = response.content.decode("utf-8")
        return json.loads(content)
    except Exception as e:
        st.error(f"Error fetching GEX profile: {e}")
        return {}

def fetch_gex_levels() -> dict:
    """Fetch GEX levels data."""
    url = _get_api_url('API_GEX_STRIKES')
    if not url: return {}
    
    try:
        response = requests.get(url=url, headers=headers, stream=True)
        response.raise_for_status()
        content = response.content.decode("utf-8")
        return json.loads(content)
    except Exception as e:
        st.error(f"Error fetching GEX levels: {e}")
        return {}

def fetch_ohlc_data() -> pd.DataFrame:
    """Fetch OHLC data."""
    url = _get_api_url('API_GEX_OHLC')
    if not url: return pd.DataFrame()
    
    try:
        response = requests.get(url=url, headers=headers, stream=True)
        response.raise_for_status()
        content = response.content.decode("utf-8")
        
        df = pd.DataFrame(json.loads(content))
        if not df.empty:
            df.set_index(['Date'], inplace=True)
            df.index = pd.to_datetime(df.index, format='%Y-%m-%dT%H:%M:%S%z', utc=True)
            df.index = pd.to_datetime(df.index.date)
        return df
    except Exception as e:
        st.error(f"Error fetching OHLC data: {e}")
        return pd.DataFrame()

