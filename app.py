import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import time
import random

# =============================================================================
# 1. SAYFA VE PROFESYONEL UX KONFİGÜRASYONU
# =============================================================================
st.set_page_config(
    page_title="Trader Workstation",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=JetBrains+Mono:wght@400;700&display=swap');
        
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        .reportview-container { background: #0a0e17; }
        
        h1, h2, h3 { 
            font-family: 'Inter', sans-serif; 
            font-weight: 800;
            letter-spacing: -0.5px;
            text-transform: uppercase;
            color: #e5e7eb;
        }
        h1 { border-bottom: 1px solid #374151; padding-bottom: 15px; margin-bottom: 25px; }
        h3 { color: #9ca3af; font-size: 1.1rem; letter-spacing: 1px;}
        
        .stButton>button { 
            width: 100%; 
            background-color: #d97706; 
            color: white; 
            font-family: 'Inter', sans-serif;
            font-weight: 600; 
            letter-spacing: 1px;
            border-radius: 2px;
            border: 1px solid #b45309;
            text-transform: uppercase;
            transition: all 0.2s ease;
        }
        .stButton>button:hover {
            background-color: #f59e0b;
            border-color: #d97706;
        }
        
        code, .stCodeBlock code {
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-size: 0.85em;
            color: #d1d5db;
        }
        
        div[data-testid="stExpander"] { background-color: #111827; border: 1px solid #1f2937; border-radius: 2px;}
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. GLOBAL KONFİGÜRASYONLAR
# -----------------------------------------------------------------------------
MARKET_CONFIGS = {
    "Türkiye (BIST)": {"tv_market": "turkey", "yf_suffix": ".IS", "tv_prefix": "BIST:"},
    "Amerika (ABD)": {"tv_market": "america", "yf_suffix": "", "tv_prefix": ""}
}

TIMEFRAME_CONFIGS = {
    "4 Saatlik (4H)": {"tv_suffix": "|240", "tv_interval": "240", "yf_interval": "1h", "resample_rule": "4h", "period": "3mo"},
    "1 Günlük (1D)": {"tv_suffix": "", "tv_interval": "D", "yf_interval": "1d", "resample_rule": None, "period": "1y"},
    "1 Haftalık (1W)": {"tv_suffix": "|1W", "tv_interval": "W", "yf_interval": "1wk", "resample_rule": None, "period": "3y"}
}

def safe_fmt(val, fmt=".2f"):
    if val is None or pd.isna(val): return "N/A"
    return f"{val:{fmt}}"

# =============================================================================
# 3. TRADINGVIEW TARZI PROFESYONEL GRAFİK MOTORLARI (MUM GRAFİKLER)
# =============================================================================
def draw_trader_chart(symbol, df_target):
    df = df_target.tail(90).copy() 
    df['sma20'] = df['close'].rolling(20).mean()
    df['sma50'] = df['close'].rolling(50).mean()
    df['sma200'] = df['close'].rolling(200).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['hist'] = df['macd'] - df['signal']
    
    plt.style.use('dark_background')
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(15, 12), sharex=True, gridspec_kw={'height_ratios': [3, 1, 1, 1]})
    fig.suptitle(f"{symbol} | PROFESYONEL TRADER EKRANI", fontsize=14, fontweight='bold', color='#d97706')
    
    up = df['close'] >= df['open']
    down = df['close'] < df['open']
    width = 0.6
    
    ax1.bar(df.index[up], df['close'][up] - df['open'][up], width, bottom=df['open'][up], color='#10b981', edgecolor='#10b981', alpha=0.9)
    ax1.bar(df.index[down], df['open'][down] - df['close'][down], width, bottom=df['close'][down], color='#ef4444', edgecolor='#ef4444', alpha=0.9)
    ax1.vlines(df.index[up], df['low'][up], df['high'][up], color='#10b981', linewidth=1)
    ax1.vlines(df.index[down], df['low'][down], df['high'][down], color='#ef4444', linewidth=1)
    
    ax1.plot(df.index, df['sma20'], color='#00ffff', label='SMA 20', linestyle='--', linewidth=1)
    ax1.plot(df.index, df['sma50'], color='#ff00ff', label='SMA 50', linestyle='--', linewidth=1)
    ax1.plot(df.index, df['sma200'], color='#ffff00', label='SMA 200', linestyle='-', linewidth=1.2)
    ax1.set_title("FIYAT TRENDI & HAREKETLI ORTALAMALAR", color='#9ca3af', loc='left', fontsize=10)
    ax1.legend(loc='upper left', frameon=False)
    ax1.grid(True, alpha=0.1)
    
    colors_vol = ['#10b981' if c else '#ef4444' for c in up]
    colors_vol[-3], colors_vol[-2], colors_vol[-1] = '#374151', '#6b7280', '#00ffff' 
    ax2.bar(df.index, df['volume'], color=colors_vol, width=0.6, alpha=0.85)
    ax2.set_title("HACIM DAGILIMI (V3 > V2 > V1)", color='#9ca3af', loc='left', fontsize=10)
    ax2.grid(True, alpha=0.1)
    
    ax3.plot(df.index, df['rsi'], color='#8b5cf6', linewidth=1.5)
    ax3.axhline(50, color='#ffffff', linestyle=':', alpha=0.3)
    ax3.fill_between(df.index, df['rsi'], 50, where=(df['rsi'] >= 50), color='#8b5cf6', alpha=0.1)
    ax3.set_title("GORECELI GUC ENDEKSI (RSI)", color='#9ca3af', loc='left', fontsize=10)
    ax3.set_ylim(10, 90)
    ax3.grid(True, alpha=0.1)
    
    ax4.plot(df.index, df['macd'], color='#06b6d4', label='MACD', linewidth=1.2)
    ax4.plot(df.index, df['signal'], color='#f43f5e', label='Sinyal', linewidth=1.2)
    ax4.bar(df.index, df['hist'], color=['#10b981' if x >= 0 else '#ef4444' for x in df['hist']], width=0.5, alpha=0.5)
    ax4.axhline(0, color='#ffffff', linestyle='-', alpha=0.2)
    ax4.set_title("MACD KESISIMI", color='#9ca3af', loc='left', fontsize=10)
    ax4.legend(loc='upper left', frameon=False)
    ax4.grid(True, alpha=0.1)
    
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    fig.autofmt_xdate()
    plt.tight_layout()
    return fig

def draw_macro_trend_chart(symbol, df_target, context):
    lookback_bars = context.get('lookback_bars', 200)
    df = df_target.tail(lookback_bars).copy() 
    df.columns = [str(c).lower() for c in df.columns] 
    
    plt.style.use('dark_background')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 9), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
    fig.suptitle(f"{symbol} | MAKRO TREND KIRILIMI (HAFTALIK)", fontsize=14, fontweight='bold', color='#10b981')
    
    up = df['close'] >= df['open']
    down = df['close'] < df['open']
    width = 4 
    
    ax1.bar(df.index[up], df['close'][up] - df['open'][up], width, bottom=df['open'][up], color='#10b981', edgecolor='#10b981', alpha=0.9)
    ax1.bar(df.index[down], df['open'][down] - df['close'][down], width, bottom=df['close'][down], color='#ef4444', edgecolor='#ef4444', alpha=0.9)
    ax1.vlines(df.index[up], df['low'][up], df['high'][up], color='#10b981', linewidth=1.5)
    ax1.vlines(df.index[down], df['low'][down], df['high'][down], color='#ef4444', linewidth=1.5)
    
    u_start_b = context['u_start_b']
    max_u_slope = context['max_u_slope']
    u_start_p = context['u_start_p']
    
    trend_dates = df.index[u_start_b:]
    trend_prices = [u_start_p + max_u_slope * (i - u_start_b) for i in range(u_start_b, len(df))]
    
    ax1.plot(trend_dates, trend_prices, color='#f59e0b', linewidth=2.5, linestyle='--', label='Kırılan Ana Direnç')
    ax1.scatter(df.index[u_start_b], u_start_p, color='#f59e0b', s=100, zorder=5, label='Tarihi Zirve') 
    
    ax1.scatter(df.index[-1], df['high'].iloc[-1] * 1.05, color='#00ffff', marker='v', s=150, zorder=5, label='Kırılım Onayı')
    
    ax1.set_title("UZUN VADELİ BASKI VE YUKARI KOPUŞ", color='#9ca3af', loc='left', fontsize=10)
    ax1.legend(loc='upper right', frameon=False)
    ax1.grid(True, alpha=0.1)
    
    colors_vol = ['#1f77b4'] * len(df)
    colors_vol[-1] = '#f59e0b' 
    ax2.bar(df.index, df['volume'], color=colors_vol, width=4, alpha=0.85)
    
    avg_vol = df['volume'].iloc[-5:-1].mean()
    ax2.axhline(avg_vol * 1.5, color='#10b981', linestyle=':', linewidth=2, label='+%50 Kurumsal Hacim Şartı')
    
    ax2.set_title(f"HACİM PATLAMASI (+%{context['vol_increase']:.0f})", color='#9ca3af', loc='left', fontsize=10)
    ax2.legend(loc='upper left', frameon=False)
    ax2.grid(True, alpha=0.1)
    
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    fig.autofmt_xdate()
    plt.tight_layout()
    return fig

def draw_tab3_dynamic_chart(symbol, df_target, template_data):
    df = df_target.tail(120).copy()
    
    df['SMA50'] = df['close'].rolling(50).mean()
    df['SMA200'] = df['close'].rolling(200).mean()
    df['EMA5'] = df['close'].ewm(span=5, adjust=False).mean()
    df['EMA20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    df['BB_mid'] = df['close'].rolling(20).mean()
    df['BB_std'] = df['close'].rolling(20).std()
    df['BB_up'] = df['BB_mid'] + 2 * df['BB_std']
    df['BB_low'] = df['BB_mid'] - 2 * df['BB_std']
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    
    desc = (template_data.get('amacı', '') + " " + template_data.get('hedefi', '') + " " + template_data.get('beklenti', '')).lower()
    
    plt.style.use('dark_background')
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 10), sharex=True, gridspec_kw={'height_ratios': [3, 1, 1]})
    fig.suptitle(f"{symbol} | KANTİTATİF ŞABLON TEYİT EKRANI", fontsize=14, fontweight='bold', color='#8b5cf6')
    
    up = df['close'] >= df['open']
    down = df['close'] < df['open']
    width = 0.6
    
    ax1.bar(df.index[up], df['close'][up] - df['open'][up], width, bottom=df['open'][up], color='#10b981', edgecolor='#10b981')
    ax1.bar(df.index[down], df['open'][down] - df['close'][down], width, bottom=df['close'][down], color='#ef4444', edgecolor='#ef4444')
    ax1.vlines(df.index[up], df['low'][up], df['high'][up], color='#10b981', linewidth=1)
    ax1.vlines(df.index[down], df['low'][down], df['high'][down], color='#ef4444', linewidth=1)
    
    if "ema" in desc or "ema5" in desc or "ema20" in desc or "ema50" in desc:
        ax1.plot(df.index, df['EMA5'], color='#f472b6', label='EMA 5 (Kısa İvme)', linewidth=1.2)
        ax1.plot(df.index, df['EMA20'], color='#60a5fa', label='EMA 20 (Destek)', linewidth=1.2)
        ax1.plot(df.index, df['EMA50'], color='#f59e0b', label='EMA 50 (Ana Yön)', linewidth=1.2)
        
    if "sma" in desc or "sma50" in desc or "sma200" in desc or "kurumsal" in desc or "stage 2" in desc:
        ax1.plot(df.index, df['SMA50'], color='#f59e0b', label='SMA 50', linestyle='--', linewidth=1.5)
        ax1.plot(df.index, df['SMA200'], color='#eab308', label='SMA 200 (Makro Yön)', linewidth=1.5)
        
    if "bollinger" in desc or "sıkışma" in desc or "vcp" in desc or "daralma" in desc or "bant" in desc:
        ax1.plot(df.index, df['BB_up'], color='#94a3b8', linestyle=':', label='BB Üst Bant')
        ax1.plot(df.index, df['BB_low'], color='#94a3b8', linestyle=':')
        ax1.fill_between(df.index, df['BB_up'], df['BB_low'], color='#94a3b8', alpha=0.08)
        
    ax1.legend(loc='upper left', frameon=False)
    ax1.set_title("FIYAT VE DİNAMİK FİLTRE GÖSTERGELERİ", color='#9ca3af', loc='left', fontsize=10)
    ax1.grid(True, alpha=0.1)
    
    colors_vol = ['#10b981' if c else '#ef4444' for c in up]
    if "hacim" in desc or "rel vol" in desc:
        colors_vol[-1] = '#00ffff' 
    ax2.bar(df.index, df['volume'], color=colors_vol, width=0.6, alpha=0.85)
    ax2.set_title("HACİM DESTEĞİ", color='#9ca3af', loc='left', fontsize=10)
    ax2.grid(True, alpha=0.1)
    
    ax3.plot(df.index, df['rsi'], color='#8b5cf6', linewidth=1.5)
    ax3.axhline(50, color='#ffffff', linestyle=':', alpha=0.3)
    if "aşırı" in desc or "rsi" in desc:
        ax3.fill_between(df.index, df['rsi'], 50, where=(df['rsi'] >= 50), color='#8b5cf6', alpha=0.15)
    ax3.set_title("MOMENTUM (RSI 14)", color='#9ca3af', loc='left', fontsize=10)
    ax3.set_ylim(10, 90)
    ax3.grid(True, alpha=0.1)
    
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate()
    plt.tight_layout()
    return fig

def draw_macro_fib_chart(symbol, df_target, context):
    lookback_bars = context.get('lookback_bars', 150)
    df = df_target.tail(lookback_bars).copy()
    df.columns = [str(c).lower() for c in df.columns]
    
    plt.style.use('dark_background')
    fig, ax1 = plt.subplots(1, 1, figsize=(15, 8))
    fig.suptitle(f"{symbol} | MAKRO FIBONACCI EKRANI (HAFTALIK)", fontsize=14, fontweight='bold', color='#8b5cf6')
    
    up = df['close'] >= df['open']
    down = df['close'] < df['open']
    width = 4 
    
    ax1.bar(df.index[up], df['close'][up] - df['open'][up], width, bottom=df['open'][up], color='#10b981', edgecolor='#10b981', alpha=0.9)
    ax1.bar(df.index[down], df['open'][down] - df['close'][down], width, bottom=df['close'][down], color='#ef4444', edgecolor='#ef4444', alpha=0.9)
    ax1.vlines(df.index[up], df['low'][up], df['high'][up], color='#10b981', linewidth=1.5)
    ax1.vlines(df.index[down], df['low'][down], df['high'][down], color='#ef4444', linewidth=1.5)
    
    ax1.axhline(context['fib_0'], color='#ef4444', linestyle='-', linewidth=1.5, alpha=0.8, label='Fib 0.0 (Makro Zirve)')
    ax1.axhline(context['fib_0382'], color='#9ca3af', linestyle='--', linewidth=1, alpha=0.5, label='Fib 0.382')
    ax1.axhline(context['fib_0500'], color='#f59e0b', linestyle='--', linewidth=1.5, alpha=0.8, label='Fib 0.500 (Denge)')
    ax1.axhline(context['fib_0618'], color='#10b981', linestyle='-', linewidth=2, alpha=0.9, label='Fib 0.618 (Golden Pocket)')
    ax1.axhline(context['fib_1'], color='#3b82f6', linestyle='-', linewidth=1.5, alpha=0.8, label='Fib 1.0 (Makro Dip)')
    
    ax1.axhspan(context['fib_0618'], context['fib_0500'], color='#f59e0b', alpha=0.15, label='Altın Bölge (Alım Alanı)')
    
    ax1.set_title(f"AŞAMA: {context['phase']}", color='#9ca3af', loc='left', fontsize=11, fontweight='bold')
    ax1.legend(loc='upper left', frameon=False)
    ax1.grid(True, alpha=0.1)
    
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    fig.autofmt_xdate()
    plt.tight_layout()
    return fig

# =============================================================================
# 4. API VE TEMEL TARAMA FONKSİYONLARI 
# =============================================================================
def scan_tradingview_by_timeframe(tf_config, mkt_config):
    url = f"https://scanner.tradingview.com/{mkt_config['tv_market']}/scan"
    sfx = tf_config["tv_suffix"]
    payload = {
        "filter": [
            {"left": "market", "operation": "equal", "right": mkt_config['tv_market']},
            {"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]},
            {"left": f"RSI{sfx}", "operation": "greater", "right": 50},
            {"left": f"MACD.macd{sfx}", "operation": "greater", "right": f"MACD.signal{sfx}"},
            {"left": f"close{sfx}", "operation": "greater", "right": f"SMA20{sfx}"},
            {"left": f"close{sfx}", "operation": "greater", "right": f"SMA50{sfx}"},
            {"left": f"close{sfx}", "operation": "greater", "right": f"SMA200{sfx}"}
        ],
        "options": {"lang": "en"}, "markets": [mkt_config['tv_market']],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", f"close{sfx}", f"RSI{sfx}", f"MACD.macd{sfx}", f"MACD.signal{sfx}", f"SMA20{sfx}", f"SMA50{sfx}", f"SMA200{sfx}"],
        "sort": {"sortBy": "name", "sortOrder": "asc"}, "range": [0, 450] 
    }
    try:
        response = requests.post(url, json=payload, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if response.status_code == 200:
            data = response.json().get("data", [])
            return {item["d"][0]: {"tv_close": item["d"][1], "rsi": item["d"][2], "macd": item["d"][3], "signal": item["d"][4], "sma20": item["d"][5], "sma50": item["d"][6], "sma200": item["d"][7]} for item in data}
        return {}
    except Exception: return {}

def check_yfinance_volume_condition(symbol, tf_config, mkt_config):
    clean_symbol = symbol.replace('.', '-')
    yf_ticker = f"{clean_symbol}{mkt_config['yf_suffix']}"
    try:
        df = yf.download(tickers=yf_ticker, period=tf_config["period"], interval=tf_config["yf_interval"], progress=False)
        if df.empty: return False, None, None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        df = df[['open', 'high', 'low', 'close', 'volume']].copy()
        
        if tf_config["resample_rule"] == "4h": df_target = df.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        else: df_target = df.dropna()
            
        if len(df_target) < 3: return False, None, None
        v1, v2, v3 = float(df_target["volume"].iloc[-3]), float(df_target["volume"].iloc[-2]), float(df_target["volume"].iloc[-1])
        v_data = {"price": float(df_target["close"].iloc[-1]), "v1": v1, "v2": v2, "v3": v3}
        return (v3 > v2 > v1), v_data, df_target
    except Exception: return False, None, None

def get_all_market_symbols(mkt_config):
    url = f"https://scanner.tradingview.com/{mkt_config['tv_market']}/scan"
    payload = {
        "filter": [{"left": "type", "operation": "in_range", "right": ["stock"]}],
        "options": {"lang": "en"}, "markets": [mkt_config['tv_market']],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "market_cap_basic"],
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"}, 
        "range": [0, 600]
    }
    try:
        resp = requests.post(url, json=payload, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if resp.status_code == 200: return [item["d"][0] for item in resp.json().get("data", [])]
    except: pass
    return []

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_macro_data_cached(tickers):
    return yf.download(tickers=tickers, period="5y", interval="1wk", group_by="ticker", threads=True, progress=False)

def evaluate_macro_trader_breakout(df, lookback_bars=200):
    if df is None or len(df) < lookback_bars: return False, None
    
    df_calc = df.tail(lookback_bars).copy()
    highs = df_calc['High'].values
    closes = df_calc['Close'].values
    opens = df_calc['Open'].values
    volumes = df_calc['Volume'].values
    
    curr_idx = len(highs) - 1
    prev_idx = curr_idx - 1
    
    min_peak_age = 26
    end_search_peak = curr_idx - min_peak_age
    
    if end_search_peak <= 0: return False, None
    
    u_start_b = np.argmax(highs[:end_search_peak])
    u_start_p = highs[u_start_b]
    
    if closes[curr_idx] > u_start_p:
        return False, None
        
    max_u_slope = -np.inf
    u_sec_b = -1
    
    search_end_slope = curr_idx - 4
    for i in range(u_start_b + 1, search_end_slope):
        slope = (highs[i] - u_start_p) / (i - u_start_b)
        if slope > max_u_slope:
            max_u_slope = slope
            u_sec_b = i
            
    if u_sec_b == -1 or max_u_slope >= 0:
        return False, None
        
    prev_trendline = u_start_p + max_u_slope * (prev_idx - u_start_b)
    curr_trendline = u_start_p + max_u_slope * (curr_idx - u_start_b)
    
    if closes[prev_idx] >= prev_trendline:
        return False, None
        
    if closes[curr_idx] <= curr_trendline:
        return False, None
        
    for i in range(curr_idx - 4, prev_idx):
        trend_at_i = u_start_p + max_u_slope * (i - u_start_b)
        if closes[i] > trend_at_i:
            return False, None
            
    is_green_candle = closes[curr_idx] > opens[curr_idx]
    if not is_green_candle:
        return False, None
        
    avg_vol_1m = np.mean(volumes[curr_idx-5 : curr_idx-1])
    curr_vol = volumes[curr_idx]
    
    if avg_vol_1m <= 0 or curr_vol <= (avg_vol_1m * 1.5):
        return False, None
        
    vol_increase_pct = ((curr_vol / avg_vol_1m) - 1) * 100
    
    return True, {
        "price": closes[curr_idx], 
        "trend_val": curr_trendline, 
        "u_start_p": u_start_p, 
        "u_start_b": u_start_b, 
        "max_u_slope": max_u_slope, 
        "vol_increase": vol_increase_pct,
        "lookback_bars": lookback_bars 
    }

def evaluate_macro_fibonacci(df, lookback_bars=150):
    if df is None or len(df) < 50: return False, None
    df_calc = df.tail(lookback_bars).copy()
    highs, lows, closes, opens = df_calc['High'].values, df_calc['Low'].values, df_calc['Close'].values, df_calc['Open'].values
    
    min_idx = np.argmin(lows)
    if min_idx >= len(highs) - 5: return False, None 
    
    max_idx = min_idx + np.argmax(highs[min_idx : -4])
    swing_high, swing_low = highs[max_idx], lows[min_idx]
    diff = swing_high - swing_low
    if diff <= 0: return False, None
    
    fib_0 = swing_high
    fib_0382 = swing_high - 0.382 * diff
    fib_0500 = swing_high - 0.500 * diff
    fib_0618 = swing_high - 0.618 * diff
    fib_0786 = swing_high - 0.786 * diff
    fib_1 = swing_low
    fib_ext_1618 = swing_high + 0.618 * diff
    
    curr_close, curr_open = closes[-1], opens[-1]
    
    in_golden_zone = (fib_0618 <= curr_close <= fib_0500)
    dist_0500, dist_0618 = abs(curr_close - fib_0500) / fib_0500, abs(curr_close - fib_0618) / fib_0618
    near_golden_zone = (dist_0500 < 0.02) or (dist_0618 < 0.02)
    
    is_green_candle = curr_close > curr_open
    valid_trend = curr_close > fib_0786
    is_golden_pocket = (in_golden_zone or near_golden_zone) and is_green_candle and valid_trend
    
    # SADECE 0.618 Pullback Bölgesi Hedefleniyor (Kırılımlar elendi)
    if is_golden_pocket: 
        phase = "[ALIM ARALIĞI] 0.618 Pullback"
        return True, {
            "phase": phase, "price": curr_close, "fib_0": fib_0, "fib_0382": fib_0382, 
            "fib_0500": fib_0500, "fib_0618": fib_0618, "fib_1": fib_1, "fib_target": fib_ext_1618, 
            "lookback_bars": lookback_bars
        }
        
    return False, None

# =============================================================================
# 5. KANTİTATİF LABORATUVAR VERİ YAPISI
# =============================================================================
TAB5_TEMPLATES = {
    "[ŞABLON 1] Mikro Trend Dönüşü (Erken Sinyal)": {"amacı": "Çok kısa vadeli momentumun (EMA 5), orta vadeli trendi (EMA 50) yukarı kestiği o ilk sismik anı bulmaktır.", "hedefi": "Fiyat dipte konsolide olduktan sonra başlayan ilk agresif hareketi yakalamak.", "beklenti": "Fiyatın dipten yeni kalkıyor olması ve MACD'nin tam sıfır noktasında kesişim yapıyor olması gözlenmelidir.", "tv_filters": [{"left": "EMA5", "operation": "greater", "right": "EMA50"}, {"left": "MACD.macd", "operation": "greater", "right": "MACD.signal"}]},
    "[ŞABLON 2] Kusursuz Sıralanım (Minervini)": {"amacı": "Bir hissenin tartışmasız ve en güçlü Boğa Piyasasında olduğunu matematiksel olarak ispatlamaktır.", "hedefi": "Ortalamaların büyükten küçüğe sıralandığı (SMA 50 > 100 > 200) lider hisselere fon girişi yapmak.", "beklenti": "ADX'in 20'den büyük olmasıyla trend gücünün kanıtlanması ve kurumsal hacim artışı.", "tv_filters": [{"left": "SMA50", "operation": "greater", "right": "SMA100"}, {"left": "SMA100", "operation": "greater", "right": "SMA200"}, {"left": "close", "operation": "greater", "right": "SMA50"}, {"left": "ADX", "operation": "greater", "right": 20}]},
    "[ŞABLON 3] VCP (Volatilite Daralması) Pususu": {"amacı": "Fiyatın sert bir yükselişten sonra dinlenmeye geçtiği, hacmin kuruduğu alanı bulmaktır.", "hedefi": "Yön bulmakta zorlanan, sıkışmış ve patlamaya hazır (Accumulation) evresindeki hisseyi yakalamak.", "beklenti": "Volatilitenin %15 altına düşmesi ve işlem hacminin kuruyarak satıcıların bittiğini teyit etmesi.", "tv_filters": [{"left": "close", "operation": "greater", "right": "EMA20"}, {"left": "ADX", "operation": "less", "right": 20}, {"left": "Volatility.D", "operation": "less", "right": 15}]},
    "[ŞABLON 4] Yatay Kırılım (Sıkışma Patlaması)": {"amacı": "Son 1 haftadır daracık bir bantta sıkışmış hissenin hacimle o kutudan yukarı fırlamasını avlamaktır.", "hedefi": "Gün içi veya kısa vadeli (Swing) sert patlamaları tam kırılım anında yakalamak.", "beklenti": "Relatif Hacmin (Rel Vol) en az 1.2 katına çıkması ve RSI'ın 50 üzerine atması.", "tv_filters": [{"left": "relative_volume_10d_calc", "operation": "greater", "right": 1.2}, {"left": "ADX", "operation": "less", "right": 20}, {"left": "RSI", "operation": "greater", "right": 50}]},
    "[ŞABLON 5] Aşırı Sıkışma (Yay Gerilmesi)": {"amacı": "Volatilitenin çift kademeli (%15 ve %5 altı) düşerek fiyatın düz bir çizgi haline geldiği ölüm sessizliğini taramak.", "hedefi": "Yayı sonuna kadar gerilmiş hisseye, hacim girdiği saniye girip asimetrik kâr almak.", "beklenti": "Müthiş dar bir stop-loss mesafesi ve anlık hacim (Rel Vol > 1.2) patlaması.", "tv_filters": [{"left": "Volatility.D", "operation": "less", "right": 5}, {"left": "ADX", "operation": "less", "right": 20}, {"left": "relative_volume_10d_calc", "operation": "greater", "right": 1.2}]},
    "[ŞABLON 6] Makro Ralli ve Yüksek Beta": {"amacı": "Endeksten agresif hareket eden (Beta > 0.8), yılbaşından beri makro ralliye girmiş hisseleri listelemektir.", "hedefi": "Fon yöneticilerinin ağırlık verdiği, ivmeli lider hisseleri portföye eklemek.", "beklenti": "Fiyatın SMA 200 üzerinde süzülmesi ve ADX'in 25 üzerinde ralli modunda kalması.", "tv_filters": [{"left": "close", "operation": "greater", "right": "SMA200"}, {"left": "SMA50", "operation": "greater", "right": "SMA200"}, {"left": "ADX", "operation": "greater", "right": 25}]},
    "[ŞABLON 7] Bayrak Flama (Pullback) Düzeltmesi": {"amacı": "Son 1 ayda çok yükselmiş ancak son 1 haftada yorulup dinlenmeye (Bayrak) geçmiş hisseleri bulmaktır.", "hedefi": "Trendi kaçırmadan, trende 'ilk güvenli geri çekilme' noktasından binme şansı sunmak.", "beklenti": "RSI'ın 50-70 bandına soğuması ve ADX'in hala 20 üzerinde gücünü koruması.", "tv_filters": [{"left": "SMA50", "operation": "greater", "right": "SMA200"}, {"left": "ADX", "operation": "greater", "right": 20}, {"left": "Perf.1M", "operation": "greater", "right": 15}]},
    "[ŞABLON 8] Ayı Piyasası (Açığa Satış Çöküşü)": {"amacı": "Aylardır yükselen ancak son 1 ayda zirveden yıkılmaya başlayan hisseleri tespit etmektir.", "hedefi": "Açığa satış (Short) yapmak veya eldeki portföyü boşaltmak için alarm mekanizması.", "beklenti": "Fiyatın EMA 20 ve SMA 50'nin altına sarkması ve bu esnada hacmin artması.", "tv_filters": [{"left": "close", "operation": "less", "right": "EMA20"}, {"left": "MACD.macd", "operation": "less", "right": "MACD.signal"}, {"left": "Perf.3M", "operation": "greater", "right": 0}, {"left": "Perf.1M", "operation": "less", "right": 0}]},
    "[ŞABLON 9] Agresif Momentum (Çoklu Teyit)": {"amacı": "Piyasada anlık olarak en sıcak olan, tüm momentum indikatörlerinin al sinyali verdiği tahtaları bulmak.", "hedefi": "Haftalık %15'ten fazla uçmamış ama gün içi agresif para giren hisselerde scalp/swing yapmak.", "beklenti": "CCI > 90 ve güçlü Aroon ile alıcıların hissede tam kontrol sağladığının teyidi.", "tv_filters": [{"left": "EMA5", "operation": "greater", "right": "EMA20"}, {"left": "CCI20", "operation": "greater", "right": 90}, {"left": "Aroon.Up", "operation": "greater", "right": "Aroon.Down"}]},
    "[ŞABLON 10] Erken Trend Teyidi ve SAR Onayı": {"amacı": "Parabolik SAR indikatörünün fiyatın altına geçerek teknik düşüşü bitirdiği ilk evreyi tarar.", "hedefi": "Trend dönüşünü erkenden ve risksiz şekilde teyit etmek.", "beklenti": "SAR dönüşü ile birlikte CCI > 90 onayı ve göreceli hacmin 1'in üzerinde kalması.", "tv_filters": [{"left": "EMA5", "operation": "greater", "right": "EMA50"}, {"left": "CCI20", "operation": "greater", "right": 90}, {"left": "MACD.macd", "operation": "greater", "right": "MACD.signal"}]},
    "[ŞABLON 11] Standart Salınım (Swing) Temeli": {"amacı": "Aşırı uçlarda olmayan, sağlıklı bir şekilde yönünü yukarı çevirmiş şirketleri listelemektir.", "hedefi": "CCI > -100 ile aşırı satımdan (oversold) yeni kurtulmuş hisselerde güvenli dalga sörfü.", "beklenti": "Relatif hacim artışı ve EMA'ların pozitif sıralanması.", "tv_filters": [{"left": "EMA5", "operation": "greater", "right": "EMA50"}, {"left": "CCI20", "operation": "greater", "right": -100}, {"left": "RSI", "operation": "greater", "right": 50}]},
    "[ŞABLON 12] Kurumsal Trend (Stage 2) Onayı": {"amacı": "Kurumsal fonların ağırlık verdiği, tartışmasız 2. Evre (Stage 2) ralli hisselerini avlamaktır.", "hedefi": "Golden Cross (50>200) sonrası oluşan sarsılmaz trendlere katılmak.", "beklenti": "Kısa vadeli hacmin uzun vadeli hacmi geçmesi ve ADX'in trendi kanıtlaması.", "tv_filters": [{"left": "SMA50", "operation": "greater", "right": "SMA200"}, {"left": "close", "operation": "greater", "right": "SMA50"}, {"left": "ADX", "operation": "greater", "right": 25}]},
    "[ŞABLON 13] Hızlı Salınım ve Bulut (Ichimoku)": {"amacı": "Ichimoku bulut sistemindeki ilk ve en hızlı al sinyalini (Tenkan'ın Kijun'u kesmesi) yakalamaktır.", "hedefi": "1-2 günlük çok hızlı vur-kaç (fast swing) işlemleri için likit hisseler bulmak.", "beklenti": "Hacmin 1 Milyonun üzerinde olması ve 7 günlük hızlı RSI'ın aşırı alıma girmeden ivmelenmesi.", "tv_filters": [{"left": "Ichimoku.CLine", "operation": "greater", "right": "Ichimoku.BLine"}, {"left": "MACD.macd", "operation": "greater", "right": "MACD.signal"}]},
    "[ŞABLON 14] Bollinger Sıkışma Patlaması": {"amacı": "Piyasada uyuyan bir devin uyanış anını saniyesinde yakalamaktır. En agresif patlama taktiğidir.", "hedefi": "Fiyatın Bollinger Üst Bandını delip geçmesi ve hacmin patlamasıyla rallinin fişeğini ateşlemek.", "beklenti": "ADX'in 20 üzerine aniden tırmanması ve fiyatın bant dışında kapanış yapması.", "tv_filters": [{"left": "ADX", "operation": "greater", "right": 20}, {"left": "relative_volume_10d_calc", "operation": "greater", "right": 1.2}]},
    "[ŞABLON 15] Dipten Dönüş (Küllerinden Doğuş)": {"amacı": "Son 3 aydır çöken ancak son 1 ayda ana ortalamaların üzerine atarak hayata dönenleri tespit etmektir.", "hedefi": "Klasik 'Bottom Fishing' taktiği ile kötü günleri geride bırakmış şirketleri en dipte almak.", "beklenti": "Fiyatın SMA 50'yi geri kazanması ve ADX'in yeni bir yükseliş trendi teyidi vermesi.", "tv_filters": [{"left": "Perf.3M", "operation": "less", "right": 0}, {"left": "Perf.1M", "operation": "greater", "right": 5}, {"left": "close", "operation": "greater", "right": "SMA50"}]},
    "[ŞABLON 16] Şelale Başlangıcı (Düşüş Trendi)": {"amacı": "Diplerden dönüşün tam tersi senaryodur; zirveden yıkılmaya başlayan hisseleri bulur.", "hedefi": "Açığa satış (Short) sinyali veya eldeki pozisyonu kapatmak için acil durum uyarısı.", "beklenti": "Fiyatın tüm destekleri kırması ve düşerken hacmin artarak kurumsal satışı teyit etmesi.", "tv_filters": [{"left": "close", "operation": "less", "right": "EMA20"}, {"left": "Perf.1M", "operation": "less", "right": 0}, {"left": "RSI", "operation": "less", "right": 45}]},
    "[ŞABLON 17] Ultra Sıkışma ve Hacim Şoku": {"amacı": "EKG cihazındaki 'düz çizgi' misali volatilitesi ölmüş hisseye aniden giren parayı tarar.", "hedefi": "Yön ararken EMA 20 üzerine atan hissede dar stop-loss ile asimetrik kâr yakalamak.", "beklenti": "Çok düşük volatilite periyodunun ardından Rel Vol > 1.2 ile gelen hacim patlaması.", "tv_filters": [{"left": "Volatility.D", "operation": "less", "right": 5}, {"left": "relative_volume_10d_calc", "operation": "greater", "right": 1.2}, {"left": "close", "operation": "greater", "right": "EMA20"}]},
    "[ŞABLON 18] Hareketli Ortalama Düzeltmesi (Holy Grail)": {"amacı": "Ralliye kalkmış hissenin soluklanmak için EMA 20 desteğine geri çekildiği kusursuz alım yerini bulmak.", "hedefi": "Trendi kaçırmadan, fiyatın EMA 20'nin tam %0 ile %3 üzerinde oturduğu Risksiz Girişi yakalamak.", "beklenti": "Bütün göstergeler ralliyi kanıtlarken (ADX>20), fiyatın dinlenerek fırsat vermesi.", "tv_filters": [{"left": "EMA20", "operation": "greater", "right": "EMA50"}, {"left": "ADX", "operation": "greater", "right": 20}, {"left": "Perf.1M", "operation": "greater", "right": 10}]}
}

TAB5_CONFLUENCES = {
    "[KESİŞİM A] Kutsal Kase (Trend + İndirimli Giriş)": {"sablonlar": "Şablon 12 (Kurumsal Trend Onayı) + Şablon 18 (Hareketli Ortalama Düzeltmesi)", "mantik": "Makro olarak kusursuz bir boğa trendinde olan hissenin, mikro olarak kâr satışları yiyip EMA 20 desteğine kadar gerilediği ve tam destekten tepki aldığı noktayı tespit eder.", "neden": "Akıllı para yükselen bir hisseyi EMA 20'ye düştüğünde her zaman savunur. Stop-loss mesafeniz çok dardır, kazanma oranı (win-rate) en yüksek modellerden biridir.", "tv_filters": [{"left": "SMA50", "operation": "greater", "right": "SMA200"}, {"left": "close", "operation": "greater", "right": "EMA20"}, {"left": "ADX", "operation": "greater", "right": 25}]},
    "[KESİŞİM B] Sıkışma Patlaması (Enerji Boşalımı)": {"sablonlar": "Şablon 17 (Ultra Sıkışma) + Şablon 14 (Bollinger Patlaması)", "mantik": "Volatilitenin %5'in altına indiği, hissenin ölü taklidi yaptığı bir dönemde aniden hacim girerek fiyatın Bollinger Üst bandını parçalamasıdır.", "neden": "Fizikteki 'yay gerilmesi' prensibidir. Fiyat ne kadar uzun süre dar bir alanda sıkışırsa, kopuş o kadar şiddetli olur. Hacim geldiği saniye işleme girilir.", "tv_filters": [{"left": "Volatility.D", "operation": "less", "right": 15}, {"left": "ADX", "operation": "greater", "right": 20}, {"left": "relative_volume_10d_calc", "operation": "greater", "right": 1.2}]},
    "[KESİŞİM C] Zümrüdüanka (Küllerinden Doğuş)": {"sablonlar": "Şablon 15 (Dipten Dönüş) + Şablon 10 (Erken Trend ve SAR Onayı)", "mantik": "Aylarca düşmüş, herkesin ümidi kestiği bir hissenin aniden 50 günlük ortalamasını yukarı kırması ve tüm momentum göstergelerinin (SAR, MACD, CCI) yeşile dönmesidir.", "neden": "En devasa ralli başlangıçları, piyasanın unuttuğu hisselerde dipte başlar. Büyük fonların 'Toplama' evresini bitirip fiyatı sürmeye başladığının ilk matematiksel sinyalidir.", "tv_filters": [{"left": "Perf.3M", "operation": "less", "right": 0}, {"left": "Perf.1M", "operation": "greater", "right": 0}, {"left": "close", "operation": "greater", "right": "SMA50"}, {"left": "MACD.macd", "operation": "greater", "right": "MACD.signal"}]}
}

def scan_tab5_advanced_logic(mkt_config, tv_filter_payload):
    url = f"https://scanner.tradingview.com/{mkt_config['tv_market']}/scan"
    payload = {
        "filter": [
            {"left": "market", "operation": "equal", "right": mkt_config['tv_market']},
            {"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}
        ] + tv_filter_payload,
        "options": {"lang": "en"}, "markets": [mkt_config['tv_market']],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "close", "volume", "RSI", "MACD.macd", "MACD.signal"],
        "sort": {"sortBy": "name", "sortOrder": "asc"}, "range": [0, 450] 
    }
    try:
        response = requests.post(url, json=payload, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if response.status_code == 200:
            data = response.json().get("data", [])
            return [{"Hisse": item["d"][0], "Kapanış": safe_fmt(item["d"][1], '.2f'), "Hacim (Lot)": safe_fmt(item["d"][2], ',.0f'), "RSI": safe_fmt(item["d"][3], '.1f'), "Bağlantı": f"https://www.tradingview.com/chart/?symbol={mkt_config['tv_prefix']}{item['d'][0]}&interval=D"} for item in data]
        return []
    except Exception: return []

# =============================================================================
# UI RENDER MİMARİSİ
# =============================================================================
st.title("TRADER WORKSTATION")
tab1, tab2, tab3, tab4 = st.tabs([
    "HİBRİT TARAMA", 
    "MAKRO TREND KIRILIMI (TAM OTONOM)",
    "TARAMA FILTRELERI",
    "MAKRO FIBONACCI (HAFTALIK)"
])

# ------------------------- TAB 1 -------------------------
with tab1:
    col_mkt, col_tf, col_btn = st.columns([2, 2, 1])
    with col_mkt: t1_selected_mkt = st.selectbox("Piyasa Seçin:", list(MARKET_CONFIGS.keys()), key="t1_mkt")
    with col_tf: selected_tf = st.selectbox("Zaman Periyodu:", list(TIMEFRAME_CONFIGS.keys()), index=1)
    with col_btn: st.write("##"); execute_scan = st.button("TARAMAYI BAŞLAT", key="t1_btn")

    if "final_rows" not in st.session_state: st.session_state.final_rows = []
    if "stored_dfs" not in st.session_state: st.session_state.stored_dfs = {}
    if "last_tf" not in st.session_state: st.session_state.last_tf = ""

    if execute_scan:
        tf_config = TIMEFRAME_CONFIGS[selected_tf]
        mkt_config = MARKET_CONFIGS[t1_selected_mkt]
        st.session_state.last_tf = selected_tf
        st.session_state.final_rows = []
        st.session_state.stored_dfs = {}
        
        st.write("### SİSTEM LOG KONSOLU")
        console_placeholder = st.empty()
        progress_bar = st.progress(0)
        
        with st.spinner("TradingView API ile iletişim kuruluyor..."):
            tv_passed_stocks = scan_tradingview_by_timeframe(tf_config, mkt_config)
            
        if not tv_passed_stocks:
            st.markdown("<div style='color:#f59e0b; font-family:Inter; font-weight:600;'>[SİSTEM UYARISI] Belirtilen kriterlerde hisse bulunamadı.</div>", unsafe_allow_html=True)
        else:
            live_logs = [f"[SYSTEM]: İlk aşamayı geçen {len(tv_passed_stocks)} hisse için hacim onayı başlatıldı...\n"]
            console_placeholder.code("\n".join(live_logs))
            total_len = len(tv_passed_stocks)
            
            for idx, (symbol, tv_data) in enumerate(tv_passed_stocks.items()):
                progress_bar.progress((idx + 1) / total_len)
                is_matched, v_data, df_target = check_yfinance_volume_condition(symbol, tf_config, mkt_config)
                time.sleep(random.uniform(0.05, 0.15)) 
                
                if v_data is None: 
                    live_logs.append(f"[ERR]  {symbol:<6} : Veri bağlantısı kurulamadı.")
                    console_placeholder.code("\n".join(live_logs[-15:]))
                    continue
                    
                v1_f, v2_f, v3_f = f"{v_data['v1']:,.0f}", f"{v_data['v2']:,.0f}", f"{v_data['v3']:,.0f}"
        
                if is_matched:
                    live_logs.append(f"[OK]   {symbol:<6} : V1:{v1_f} < V2:{v2_f} < V3:{v3_f} (Hacim Onaylandı)")
                    macd_val, sig_val = tv_data['macd'], tv_data['signal']
                    macd_status = f"🔴 NEGATIF BOLGE ({macd_val:.2f}/{sig_val:.2f})" if macd_val is not None and macd_val < 0 else f"🟢 POZITIF BOLGE ({macd_val:.2f}/{sig_val:.2f})"
                    tv_prefix = mkt_config["tv_prefix"]
                    tv_url = f"https://www.tradingview.com/chart/?symbol={tv_prefix}{symbol}&interval={tf_config['tv_interval']}"
                    
                    st.session_state.final_rows.append({"Hisse": symbol, "Fiyat": round(v_data["price"], 2), "RSI (50+)": round(tv_data["rsi"], 1), "MACD Durumu": macd_status, "SMA (20/50/200)": f"{safe_fmt(tv_data['sma20'], '.1f')} / {safe_fmt(tv_data['sma50'], '.1f')} / {safe_fmt(tv_data['sma200'], '.1f')}", "V1 (T-2)": v1_f, "V2 (T-1)": v2_f, "V3 (Güncel)": v3_f, "Bağlantı": tv_url})
                    st.session_state.stored_dfs[symbol] = df_target
                else:
                    live_logs.append(f"[FAIL] {symbol:<6} : V1:{v1_f} -> V2:{v2_f} -> V3:{v3_f} (Koşul Sağlanmadı)")
                    
                console_placeholder.code("\n".join(live_logs[-15:]))
                
            st.markdown("<div style='color:#10b981; font-family:Inter; font-weight:600;'>[SİSTEM BİLGİSİ] Tarama işlemi başarıyla tamamlandı.</div>", unsafe_allow_html=True)

    if st.session_state.final_rows:
        st.write("---"); st.write(f"### ONAYLANMIŞ HİSSELER ({st.session_state.last_tf})")
        st.dataframe(pd.DataFrame(st.session_state.final_rows), use_container_width=True, hide_index=True, column_config={"Hisse": st.column_config.TextColumn("Hisse"), "Bağlantı": st.column_config.LinkColumn("TradingView", display_text="Grafiği Aç")})
        
        st.write("---"); st.write("### GRAFİK İNCELEME İSTASYONU")
        selected_stock_to_plot = st.selectbox("Detaylı inceleme için hisse seçin:", list(st.session_state.stored_dfs.keys()), key="t1_plot")
        if selected_stock_to_plot: 
            st.pyplot(draw_trader_chart(selected_stock_to_plot, st.session_state.stored_dfs[selected_stock_to_plot]))

# ------------------------- TAB 2 -------------------------
with tab2:
    st.write("### MAKRO TREND KIRILIM ")
    col_mkt2, col_btn2 = st.columns([3, 1])
    with col_mkt2: t2_selected_mkt = st.selectbox("Piyasa Seçin:", list(MARKET_CONFIGS.keys()), key="t2_mkt")
    with col_btn2: st.write("##"); run_macro_scan = st.button("TÜM PİYASAYI TARA (HAFTALIK)", key="t2_btn")
    
    if "tab2_rows" not in st.session_state: st.session_state.tab2_rows = []
    if "stored_dfs_t2" not in st.session_state: st.session_state.stored_dfs_t2 = {}
    if "stored_contexts_t2" not in st.session_state: st.session_state.stored_contexts_t2 = {}
    
    if run_macro_scan:
        mkt_config = MARKET_CONFIGS[t2_selected_mkt]
        st.session_state.tab2_rows = []
        st.session_state.stored_dfs_t2 = {}
        st.session_state.stored_contexts_t2 = {}
        
        with st.spinner(f"{t2_selected_mkt} Sembol verileri senkronize ediliyor..."):
            market_symbols = get_all_market_symbols(mkt_config)
            
        if not market_symbols:
            st.markdown("<div style='color:#ef4444; font-family:Inter; font-weight:600;'>[SİSTEM HATASI] Bağlantı hatası: Liste alınamadı.</div>", unsafe_allow_html=True)
        else:
            yf_tickers = [f"{s.replace('.', '-')}{mkt_config['yf_suffix']}" for s in market_symbols]
            
            with st.spinner(f"Makro veri havuzu oluşturuluyor ({len(market_symbols)} hisse, 5 Yıllık Haftalık Veri)..."):
                df_all = fetch_macro_data_cached(tickers=yf_tickers)
            
            with st.spinner("Fiyat hareketi ve hacim patlaması taranıyor..."):
                st.write("### SİSTEM LOG KONSOLU")
                console_placeholder = st.empty()
                p_bar = st.progress(0)
                live_logs = [f"[SYSTEM]: Makro trend analizi {len(market_symbols)} hisse için başlatıldı...\n"]
                console_placeholder.code("\n".join(live_logs))
                
                for idx, symbol in enumerate(market_symbols):
                    p_bar.progress((idx + 1) / len(market_symbols))
                    yf_ticker_key = f"{symbol.replace('.', '-')}{mkt_config['yf_suffix']}"
                    
                    if hasattr(df_all.columns, 'levels') and yf_ticker_key in df_all.columns.levels[0]:
                        df_symbol = df_all[yf_ticker_key].dropna(subset=['High', 'Close', 'Open', 'Volume'])
                        
                        is_breakout, context = evaluate_macro_trader_breakout(df_symbol, lookback_bars=200)
                        
                        if is_breakout:
                            live_logs.append(f"[🔥 DEV KIRILIM] {symbol:<6} : Hacim Oranı +%{context['vol_increase']:.0f}!")
                            tv_prefix = mkt_config["tv_prefix"]
                            tv_url = f"https://www.tradingview.com/chart/?symbol={tv_prefix}{symbol}&interval=W"
                            
                            st.session_state.tab2_rows.append({
                                "Hisse": symbol,
                                "Kapanış": round(context["price"], 2),
                                "Kırılan Direnç": round(context["trend_val"], 2),
                                "Tarihi Zirve": round(context["u_start_p"], 2),
                                "Hacim Patlaması": f"+%{context['vol_increase']:.1f}",
                                "Bağlantı": tv_url
                            })
                            st.session_state.stored_dfs_t2[symbol] = df_symbol
                            st.session_state.stored_contexts_t2[symbol] = context
                        else:
                            live_logs.append(f"[FAIL] {symbol:<6} : Makro kırılım (güncel hafta) veya hacim onayı yok.")
                    else:
                        live_logs.append(f"[SKIP] {symbol:<6} : Yeterli geçmiş veri bulunamadı.")
                        
                    console_placeholder.code("\n".join(live_logs[-15:]))
                            
            st.markdown("<div style='color:#10b981; font-family:Inter; font-weight:600;'>[SİSTEM BİLGİSİ] Strateji taraması tamamlandı.</div>", unsafe_allow_html=True)
            
    if st.session_state.tab2_rows:
        st.write("---")
        st.write(f"### 🏆 HACİMLİ MAKRO KIRILIMI ONAYLANAN HİSSELER ({t2_selected_mkt})")
        st.dataframe(pd.DataFrame(st.session_state.tab2_rows), use_container_width=True, hide_index=True,
                     column_config={
                         "Bağlantı": st.column_config.LinkColumn("TradingView (Haftalık)", display_text="Grafiği Aç")
                     })
                     
        st.write("---"); st.write("### MAKRO GRAFİK İNCELEME İSTASYONU")
        selected_stock_t2 = st.selectbox("Detaylı kırılım analizi için hisse seçin:", list(st.session_state.stored_dfs_t2.keys()), key="t2_plot")
        if selected_stock_t2: 
            df_plot = st.session_state.stored_dfs_t2[selected_stock_t2]
            ctx_plot = st.session_state.stored_contexts_t2[selected_stock_t2]
            st.pyplot(draw_macro_trend_chart(selected_stock_t2, df_plot, ctx_plot))

# ------------------------- TAB 3 -------------------------
with tab3:
    st.write("### FILTRELER ve ONERILER")
    
    sub_tab_selection = st.radio("MODÜL SEÇİMİ:", ["18 TEMEL KANTİTATİF ŞABLON", "3 KUSURSUZ KESİŞİM (CONFLUENCE)"], horizontal=True)
    st.write("---")
    
    if sub_tab_selection == "18 TEMEL KANTİTATİF ŞABLON":
        col_sel, col_empty = st.columns([2, 1])
        with col_sel:
            selected_template_key = st.selectbox("İncelemek İstediğiniz Strateji Şablonunu Seçin:", list(TAB5_TEMPLATES.keys()))
        
        active_template = TAB5_TEMPLATES[selected_template_key]
        
        with st.expander("SİSTEM MÜHENDİSLİĞİ VE TRADER NOTLARI (ŞABLON DETAYI)", expanded=True):
            st.markdown(f"<div style='color:#e5e7eb; font-size:14px; margin-bottom:10px;'><b>Ana Amacı:</b><br><span style='color:#9ca3af;'>{active_template['amacı']}</span></div>", unsafe_allow_html=True)
            st.markdown(f"<div style='color:#e5e7eb; font-size:14px; margin-bottom:10px;'><b>Trader Hedefi:</b><br><span style='color:#9ca3af;'>{active_template['hedefi']}</span></div>", unsafe_allow_html=True)
            st.markdown(f"<div style='color:#e5e7eb; font-size:14px; margin-bottom:10px;'><b>Görülmesi Gereken (Teyit):</b><br><span style='color:#10b981;'>{active_template['beklenti']}</span></div>", unsafe_allow_html=True)
            
        col_mkt5, col_btn5 = st.columns([3, 1])
        with col_mkt5:
            t5_selected_mkt = st.selectbox("Piyasa Seçin:", list(MARKET_CONFIGS.keys()), key="t5_mkt_1")
        with col_btn5:
            st.write("##")
            run_tab5_single = st.button("ŞABLONU ÇALIŞTIR", key="t5_btn_1")
            
        if "tab5_rows_single" not in st.session_state: st.session_state.tab5_rows_single = []
            
        if run_tab5_single:
            mkt_config = MARKET_CONFIGS[t5_selected_mkt]
            st.session_state.tab5_rows_single = []
            
            st.write("### SİSTEM LOG KONSOLU")
            console_placeholder = st.empty()
            live_logs = [f"[SYSTEM]: TradingView API'sine şablon sorgusu gönderiliyor...\n"]
            console_placeholder.code("\n".join(live_logs))
            
            with st.spinner("Şablon parametreleri uygulanıyor ve tarama yapılıyor..."):
                results = scan_tab5_advanced_logic(mkt_config, active_template["tv_filters"])
                st.session_state.tab5_rows_single = results
                
                if not results:
                    live_logs.append(f"[UYARI]: Şablona uyan hisse bulunamadı.")
                    console_placeholder.code("\n".join(live_logs[-15:]))
                    st.markdown("<div style='color:#f59e0b; font-family:Inter; font-weight:600;'>[SİSTEM UYARISI] Bu şablona uyan hisse bulunamadı.</div>", unsafe_allow_html=True)
                else:
                    for item in results:
                        time.sleep(0.05) 
                        live_logs.append(f"[OK]   {item['Hisse']:<6} : Teknik şartlar doğrulandı.")
                        console_placeholder.code("\n".join(live_logs[-15:]))
                    st.markdown("<div style='color:#10b981; font-family:Inter; font-weight:600;'>[SİSTEM BİLGİSİ] Tarama tamamlandı.</div>", unsafe_allow_html=True)
                    
        if st.session_state.tab5_rows_single:
            st.write("---")
            st.dataframe(pd.DataFrame(st.session_state.tab5_rows_single), use_container_width=True, hide_index=True, column_config={"Bağlantı": st.column_config.LinkColumn("TradingView", display_text="Grafiği Aç")})
            
            st.write("---"); st.write("### DİNAMİK FİLTRE ONAY EKRANI")
            symbols = [row['Hisse'] for row in st.session_state.tab5_rows_single]
            selected_stock_t3 = st.selectbox("Filtre teyidi için hisse seçin:", symbols, key="t3_single_plot")
            if selected_stock_t3:
                mkt_config = MARKET_CONFIGS[t5_selected_mkt]
                clean_sym = selected_stock_t3.replace('.', '-')
                yf_ticker = f"{clean_sym}{mkt_config['yf_suffix']}"
                with st.spinner("Koşullu grafik verisi çekiliyor..."):
                    df_plot = yf.download(tickers=yf_ticker, period="1y", interval="1d", progress=False)
                    if not df_plot.empty:
                        if isinstance(df_plot.columns, pd.MultiIndex): df_plot.columns = df_plot.columns.get_level_values(0)
                        df_plot.columns = [str(c).lower() for c in df_plot.columns]
                        st.pyplot(draw_tab3_dynamic_chart(selected_stock_t3, df_plot, active_template))

    else:
        col_sel, col_empty = st.columns([2, 1])
        with col_sel:
            selected_conf_key = st.selectbox("İncelemek İstediğiniz Kesişim Modelini Seçin:", list(TAB5_CONFLUENCES.keys()))
            
        active_conf = TAB5_CONFLUENCES[selected_conf_key]
        
        with st.expander("SİSTEM MÜHENDİSLİĞİ VE TRADER NOTLARI (KESİŞİM DETAYI)", expanded=True):
            st.markdown(f"<div style='color:#e5e7eb; font-size:14px; margin-bottom:10px;'><b>Birleştirilen Şablonlar:</b><br><span style='color:#d97706; font-weight:600;'>{active_conf['sablonlar']}</span></div>", unsafe_allow_html=True)
            st.markdown(f"<div style='color:#e5e7eb; font-size:14px; margin-bottom:10px;'><b>Kesişim Mantığı:</b><br><span style='color:#9ca3af;'>{active_conf['mantik']}</span></div>", unsafe_allow_html=True)
            st.markdown(f"<div style='color:#e5e7eb; font-size:14px; margin-bottom:10px;'><b>Neden Buradan Alınır?</b><br><span style='color:#10b981;'>{active_conf['neden']}</span></div>", unsafe_allow_html=True)
            
        col_mkt5_c, col_btn5_c = st.columns([3, 1])
        with col_mkt5_c:
            t5_selected_mkt_c = st.selectbox("Piyasa Seçin:", list(MARKET_CONFIGS.keys()), key="t5_mkt_2")
        with col_btn5_c:
            st.write("##")
            run_tab5_conf = st.button("KESİŞİMİ ÇALIŞTIR", key="t5_btn_2")
            
        if "tab5_rows_conf" not in st.session_state: st.session_state.tab5_rows_conf = []
            
        if run_tab5_conf:
            mkt_config = MARKET_CONFIGS[t5_selected_mkt_c]
            st.session_state.tab5_rows_conf = []
            
            st.write("### SİSTEM LOG KONSOLU")
            console_placeholder = st.empty()
            live_logs = [f"[SYSTEM]: TradingView API'sine kesişim sorgusu gönderiliyor...\n"]
            console_placeholder.code("\n".join(live_logs))
            
            with st.spinner("Kesişim parametreleri birleştiriliyor ve tarama yapılıyor..."):
                results = scan_tab5_advanced_logic(mkt_config, active_conf["tv_filters"])
                st.session_state.tab5_rows_conf = results
                
                if not results:
                    live_logs.append(f"[UYARI]: Kesişim modeline uyan hisse bulunamadı.")
                    console_placeholder.code("\n".join(live_logs[-15:]))
                    st.markdown("<div style='color:#f59e0b; font-family:Inter; font-weight:600;'>[SİSTEM UYARISI] Bu kesişim modeline uyan hisse bulunamadı.</div>", unsafe_allow_html=True)
                else:
                    for item in results:
                        time.sleep(0.05) 
                        live_logs.append(f"[OK]   {item['Hisse']:<6} : Kesişim şartları doğrulandı.")
                        console_placeholder.code("\n".join(live_logs[-15:]))
                    st.markdown("<div style='color:#10b981; font-family:Inter; font-weight:600;'>[SİSTEM BİLGİSİ] Tarama tamamlandı.</div>", unsafe_allow_html=True)
                    
        if st.session_state.tab5_rows_conf:
            st.write("---")
            st.dataframe(pd.DataFrame(st.session_state.tab5_rows_conf), use_container_width=True, hide_index=True, column_config={"Bağlantı": st.column_config.LinkColumn("TradingView", display_text="Grafiği Aç")})
            
            st.write("---"); st.write("### DİNAMİK FİLTRE ONAY EKRANI")
            symbols = [row['Hisse'] for row in st.session_state.tab5_rows_conf]
            selected_stock_t3_c = st.selectbox("Kesişim teyidi için hisse seçin:", symbols, key="t3_conf_plot")
            if selected_stock_t3_c:
                mkt_config = MARKET_CONFIGS[t5_selected_mkt_c]
                clean_sym = selected_stock_t3_c.replace('.', '-')
                yf_ticker = f"{clean_sym}{mkt_config['yf_suffix']}"
                with st.spinner("Koşullu grafik verisi çekiliyor..."):
                    df_plot = yf.download(tickers=yf_ticker, period="1y", interval="1d", progress=False)
                    if not df_plot.empty:
                        if isinstance(df_plot.columns, pd.MultiIndex): df_plot.columns = df_plot.columns.get_level_values(0)
                        df_plot.columns = [str(c).lower() for c in df_plot.columns]
                        mock_template = {"amacı": active_conf['sablonlar']}
                        st.pyplot(draw_tab3_dynamic_chart(selected_stock_t3_c, df_plot, mock_template))

# ------------------------- TAB 4 (YENİ) -------------------------
with tab4:
    st.write("### OTONOM MAKRO FIBONACCI AĞI (HAFTALIK)")
    
    col_mkt4, col_btn4 = st.columns([3, 1])
    with col_mkt4: t4_selected_mkt = st.selectbox("Piyasa Seçin:", list(MARKET_CONFIGS.keys()), key="t4_mkt")
    with col_btn4: st.write("##"); run_fib_scan = st.button("FIBONACCI AĞINI ÇALIŞTIR", key="t4_btn")
    
    st.markdown("""
    <div style='background-color:#111827; padding:15px; border-left:4px solid #8b5cf6; margin-bottom:20px; margin-top:10px;'>
        <div style='color:#e5e7eb; font-weight:600; font-size:14px; margin-bottom:5px;'>Makro İstatistiksel Fırsat Avcısı:</div>
        <div style='color:#9ca3af; font-size:13px;'>Haftalık Makro Veri Havuzunu kullanarak devasa bir Fibonacci ağı çizer. Uzay kırılımlarını (breakout) tamamen es geçerek sadece asimetrik kârın gizlendiği güvenli bölgeye odaklanır:</div>
        <div style='color:#8b5cf6; font-family:JetBrains Mono; font-size:12px; margin-top:8px;'>
            🎯 SADECE ODAKLANILAN AŞAMA: "[ALIM ARALIĞI] 0.618 Pullback" - Akıllı paranın kâr realizasyonu bittiği ve fiyatın Fibonacci 0.618 Altın Oranından destek alarak yeşil mum yaktığı en risksiz maliyetlenme bölgesidir.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if "tab4_rows" not in st.session_state: st.session_state.tab4_rows = []
    if "stored_dfs_t4" not in st.session_state: st.session_state.stored_dfs_t4 = {}
    if "stored_contexts_t4" not in st.session_state: st.session_state.stored_contexts_t4 = {}
    
    if run_fib_scan:
        mkt_config = MARKET_CONFIGS[t4_selected_mkt]
        st.session_state.tab4_rows = []
        st.session_state.stored_dfs_t4 = {}
        st.session_state.stored_contexts_t4 = {}
        
        with st.spinner(f"{t4_selected_mkt} Sembol verileri senkronize ediliyor..."):
            market_symbols = get_all_market_symbols(mkt_config)
            
        if not market_symbols:
            st.markdown("<div style='color:#ef4444; font-family:Inter; font-weight:600;'>[SİSTEM HATASI] Bağlantı hatası: Liste alınamadı.</div>", unsafe_allow_html=True)
        else:
            yf_tickers = [f"{s.replace('.', '-')}{mkt_config['yf_suffix']}" for s in market_symbols]
            
            with st.spinner(f"Makro veri havuzu oluşturuluyor ({len(market_symbols)} hisse, 5 Yıllık Haftalık Veri)..."):
                df_all = fetch_macro_data_cached(tickers=yf_tickers)
            
            with st.spinner("Fibonacci matrisi hesaplanıyor ve 0.618 Pullback sinyalleri taranıyor..."):
                st.write("### SİSTEM LOG KONSOLU")
                console_placeholder = st.empty()
                p_bar = st.progress(0)
                live_logs = [f"[SYSTEM]: Sadece [ALIM ARALIĞI] odaklı Fibonacci Ağı {len(market_symbols)} hisse için örülüyor...\n"]
                console_placeholder.code("\n".join(live_logs))
                
                for idx, symbol in enumerate(market_symbols):
                    p_bar.progress((idx + 1) / len(market_symbols))
                    yf_ticker_key = f"{symbol.replace('.', '-')}{mkt_config['yf_suffix']}"
                    
                    if hasattr(df_all.columns, 'levels') and yf_ticker_key in df_all.columns.levels[0]:
                        df_symbol = df_all[yf_ticker_key].dropna(subset=['High', 'Low', 'Close', 'Open'])
                        
                        is_fib_setup, context = evaluate_macro_fibonacci(df_symbol, lookback_bars=150)
                        
                        if is_fib_setup:
                            live_logs.append(f"[🎯 FIBONACCI] {symbol:<6} : {context['phase']}")
                            tv_prefix = mkt_config["tv_prefix"]
                            tv_url = f"https://www.tradingview.com/chart/?symbol={tv_prefix}{symbol}&interval=W"
                            
                            st.session_state.tab4_rows.append({
                                "Aşama / Durum": context["phase"],
                                "Hisse": symbol,
                                "Güncel Fiyat": round(context["price"], 2),
                                "Tarihi Zirve (0)": round(context["fib_0"], 2),
                                "Altın Oran (0.618)": round(context["fib_0618"], 2),
                                "Uzay Hedefi (1.618)": round(context["fib_target"], 2),
                                "Bağlantı": tv_url
                            })
                            st.session_state.stored_dfs_t4[symbol] = df_symbol
                            st.session_state.stored_contexts_t4[symbol] = context
                        else:
                            live_logs.append(f"[FAIL] {symbol:<6} : Uygun Alım Aralığı bulunamadı.")
                    else:
                        live_logs.append(f"[SKIP] {symbol:<6} : Yeterli geçmiş veri bulunamadı.")
                        
                    console_placeholder.code("\n".join(live_logs[-15:]))
                            
            st.markdown("<div style='color:#8b5cf6; font-family:Inter; font-weight:600;'>[SİSTEM BİLGİSİ] Fibonacci taraması tamamlandı.</div>", unsafe_allow_html=True)

    if st.session_state.tab4_rows:
        st.write("---")
        st.write(f"### 🎯 İSTATİSTİKSEL OLARAK ALIM BÖLGESİNDEKİ HİSSELER ({t4_selected_mkt})")
        
        res_df = pd.DataFrame(st.session_state.tab4_rows)
        res_df = res_df.sort_values(by="Aşama / Durum")
        
        st.dataframe(res_df, use_container_width=True, hide_index=True,
                     column_config={
                         "Aşama / Durum": st.column_config.TextColumn("Döngü Aşaması", width="medium"),
                         "Güncel Fiyat": st.column_config.NumberColumn("Güncel Fiyat", format="%.2f"),
                         "Tarihi Zirve (0)": st.column_config.NumberColumn("Tarihi Zirve (0.0)", format="%.2f", help="Aşılması gereken makro zirve"),
                         "Altın Oran (0.618)": st.column_config.NumberColumn("Altın Oran (0.618)", format="%.2f", help="Maksimum geri çekilme ve alım bölgesi"),
                         "Uzay Hedefi (1.618)": st.column_config.NumberColumn("Uzay Hedefi (1.618)", format="%.2f", help="Kırılım sonrası istatistiksel ana direnç (Sadece referans amaçlıdır)"),
                         "Bağlantı": st.column_config.LinkColumn("TradingView (Haftalık)", display_text="Grafiği Aç")
                     })
                     
        st.write("---"); st.write("### FIBONACCI GRAFİK İNCELEME İSTASYONU")
        selected_stock_t4 = st.selectbox("Fibonacci çizim analizi için hisse seçin:", list(st.session_state.stored_dfs_t4.keys()), key="t4_plot")
        if selected_stock_t4: 
            df_plot = st.session_state.stored_dfs_t4[selected_stock_t4]
            ctx_plot = st.session_state.stored_contexts_t4[selected_stock_t4]
            st.pyplot(draw_macro_fib_chart(selected_stock_t4, df_plot, ctx_plot))
