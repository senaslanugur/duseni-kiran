import matplotlib
# [ÖNEMLİ DEPLOYMENT AYARI]: Sunucu ortamında (headless) grafik çizimi çökmesini engeller
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import time
import random

# -----------------------------------------------------------------------------
# 1. Sayfa Konfigürasyonu (Geniş Ekran ve Koyu Bloomberg Teması)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Screener Workstation",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Özel CSS: Bloomberg terminal havası ve buton tasarımları
st.markdown("""
    <style>
        .reportview-container { background: #0b0e14; }
        .stButton>button { width: 100%; background-color: #ff9900; color: black; font-weight: bold; border-radius: 4px; }
        h1, h2, h3 { font-family: 'Consolas', 'Courier New', monospace; }
        div[data-testid="stExpander"] { background-color: #121620; border: 1px solid #1f2635; }
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. Ortak Konfigürasyonlar ve Yardımcı Fonksiyonlar
# -----------------------------------------------------------------------------
TIMEFRAME_CONFIGS = {
    "4 Saatlik (4H)": {
        "tv_suffix": "|240", "tv_interval": "240", "yf_interval": "1h", "resample_rule": "4h", "period": "3mo"
    },
    "1 Günlük (1D)": {
        "tv_suffix": "", "tv_interval": "D", "yf_interval": "1d", "resample_rule": None, "period": "1y"
    },
    "1 Haftalık (1W)": {
        "tv_suffix": "|1W", "tv_interval": "W", "yf_interval": "1wk", "resample_rule": None, "period": "3y"
    }
}

def safe_fmt(val, fmt=".2f"):
    if val is None or pd.isna(val):
        return "N/A"
    return f"{val:{fmt}}"

# -----------------------------------------------------------------------------
# 3. TAB 1: Hibrit Tarama Fonksiyonları
# -----------------------------------------------------------------------------
def scan_tradingview_by_timeframe(tf_config):
    url = "https://scanner.tradingview.com/turkey/scan"
    sfx = tf_config["tv_suffix"]
    
    payload = {
        "filter": [
            {"left": "market", "operation": "equal", "right": "turkey"},
            {"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]},
            {"left": f"RSI{sfx}", "operation": "greater", "right": 50},
            {"left": f"MACD.macd{sfx}", "operation": "greater", "right": f"MACD.signal{sfx}"},
            {"left": f"close{sfx}", "operation": "greater", "right": f"SMA20{sfx}"},
            {"left": f"close{sfx}", "operation": "greater", "right": f"SMA50{sfx}"},
            {"left": f"close{sfx}", "operation": "greater", "right": f"SMA200{sfx}"}
        ],
        "options": {"lang": "en"},
        "markets": ["turkey"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": [
            "name", f"close{sfx}", f"RSI{sfx}", f"MACD.macd{sfx}", f"MACD.signal{sfx}", 
            f"SMA20{sfx}", f"SMA50{sfx}", f"SMA200{sfx}"
        ],
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, 450]
    }
    
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json().get("data", [])
            return {item["d"][0]: {
                "tv_close": item["d"][1], "rsi": item["d"][2], "macd": item["d"][3], "signal": item["d"][4],
                "sma20": item["d"][5], "sma50": item["d"][6], "sma200": item["d"][7]
            } for item in data}
        return {}
    except Exception:
        return {}

def check_yfinance_volume_condition(symbol, tf_config):
    yf_ticker = f"{symbol}.IS"
    try:
        df = yf.download(tickers=yf_ticker, period=tf_config["period"], interval=tf_config["yf_interval"], progress=False)
        if df.empty: return False, None, None
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df.columns = [c.lower() for c in df.columns]
        df = df[['open', 'high', 'low', 'close', 'volume']].copy()
        
        if tf_config["resample_rule"] == "4h":
            df_target = df.resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        else:
            df_target = df.dropna()
            
        if len(df_target) < 3: return False, None, None
            
        v1, v2, v3 = float(df_target["volume"].iloc[-3]), float(df_target["volume"].iloc[-2]), float(df_target["volume"].iloc[-1])
        last_price = float(df_target["close"].iloc[-1])
        
        v_data = {"price": last_price, "v1": v1, "v2": v2, "v3": v3}
        is_passed = (v3 > v2 > v1)
        
        return is_passed, v_data, df_target
    except Exception:
        return False, None, None

def draw_trader_chart(symbol, df_target):
    df = df_target.tail(60).copy()
    df['sma20'] = df['close'].rolling(20).mean()
    df['sma50'] = df['close'].rolling(50).mean()
    df['sma200'] = df['close'].rolling(200).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['hist'] = df['macd'] - df['signal']
    
    plt.style.use('dark_background')
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(15, 12), sharex=True, gridspec_kw={'height_ratios': [3, 1.2, 1.2, 1.2]})
    fig.suptitle(f"🔬 {symbol} DETAYLI TEKNİK ANALİZ WORKSTATION", fontsize=16, fontweight='bold', color='#ff9900')
    
    ax1.plot(df.index, df['close'], color='#ffffff', label='Kapanış', linewidth=1.5)
    ax1.plot(df.index, df['sma20'], color='#00ffff', label='SMA 20', linestyle='--', linewidth=1)
    ax1.plot(df.index, df['sma50'], color='#ff00ff', label='SMA 50', linestyle='--', linewidth=1)
    ax1.plot(df.index, df['sma200'], color='#ffff00', label='SMA 200', linestyle='-', linewidth=1.2)
    ax1.set_title("Fiyat Trendi & Hareketli Ortalamalar", color='#ff9900', loc='left')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.15)
    
    colors = ['#1f77b4'] * len(df)
    colors[-3], colors[-2], colors[-1] = '#1a5f7a', '#2d8bba', '#00ff66'
    ax2.bar(df.index, df['volume'], color=colors, width=0.6, alpha=0.85)
    ax2.set_title("Hacim Dağılımı (V3 > V2 > V1)", color='#ff9900', loc='left')
    ax2.grid(True, alpha=0.15)
    
    ax3.plot(df.index, df['rsi'], color='#ff99f8', linewidth=1.5, label='RSI (14)')
    ax3.axhline(50, color='#ffffff', linestyle=':', alpha=0.5)
    ax3.fill_between(df.index, df['rsi'], 50, where=(df['rsi'] >= 50), color='#ff99f8', alpha=0.1)
    ax3.set_title("RSI Güç Endeksi", color='#ff9900', loc='left')
    ax3.set_ylim(10, 90)
    ax3.grid(True, alpha=0.15)
    
    ax4.plot(df.index, df['macd'], color='#00ffcc', label='MACD', linewidth=1.2)
    ax4.plot(df.index, df['signal'], color='#ff3366', label='Sinyal', linewidth=1.2)
    hist_colors = ['#00ff66' if x >= 0 else '#ff3333' for x in df['hist']]
    ax4.bar(df.index, df['hist'], color=hist_colors, width=0.5, alpha=0.5, label='Histogram')
    ax4.axhline(0, color='#ffffff', linestyle='-', alpha=0.3)
    ax4.set_title("MACD", color='#ff9900', loc='left')
    ax4.legend(loc='upper left')
    ax4.grid(True, alpha=0.15)
    
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    fig.autofmt_xdate()
    plt.tight_layout()
    return fig

# -----------------------------------------------------------------------------
# 4. TAB 2: Pine Script Python Çevirisi (Düşeni Kıran / Pivot Breakout)
# -----------------------------------------------------------------------------
def get_all_bist_symbols():
    """Tüm BIST hisselerinin sembollerini TradingView üzerinden hızlıca çeker"""
    url = "https://scanner.tradingview.com/turkey/scan"
    payload = {
        "filter": [{"left": "type", "operation": "in_range", "right": ["stock"]}],
        "options": {"lang": "en"}, "markets": ["turkey"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name"], "range": [0, 600]
    }
    try:
        resp = requests.post(url, json=payload, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            return [item["d"][0] for item in resp.json().get("data", [])]
    except:
        pass
    return []

# [ÖNEMLİ DEPLOYMENT AYARI]: Sunucu RAM ve CPU limitlerini korumak için Yahoo verisini 1 saat önbellekte tutar
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_all_bist_data_cached(tickers):
    return yf.download(tickers=tickers, period="6mo", interval="1d", group_by="ticker", threads=True, progress=False)

def evaluate_pine_script_logic(df, left_bars, right_bars):
    """Pine Script mantığının Python (Pandas/Numpy) karşılığı."""
    if df is None or len(df) < left_bars + right_bars + 2:
        return False, None
    
    highs = df['High'].values
    closes = df['Close'].values
    opens = df['Open'].values
    
    pivots = []
    for i in range(left_bars, len(highs) - right_bars):
        window = highs[i - left_bars : i + right_bars + 1]
        if highs[i] == max(window):
            pivots.append((i, highs[i]))
            
    if len(pivots) < 2:
        return False, None
        
    p1_idx, p1_price = pivots[-1] 
    p2_idx, p2_price = pivots[-2] 
    
    if p2_price <= p1_price:
        return False, None 
        
    slope = (p1_price - p2_price) / (p1_idx - p2_idx)
    
    curr_idx = len(highs) - 1
    prev_idx = curr_idx - 1
    
    prev_trendline = p1_price + slope * (prev_idx - p1_idx)
    curr_trendline = p1_price + slope * (curr_idx - p1_idx)
    
    prev_close = closes[prev_idx]
    curr_close = closes[curr_idx]
    curr_open = opens[curr_idx]
    
    is_breakout = (prev_close < prev_trendline) and (curr_close > curr_trendline) and (curr_close > curr_open)
    
    context = {
        "price": curr_close,
        "trend_val": curr_trendline,
        "p1_price": p1_price,
        "p2_price": p2_price
    }
    
    return is_breakout, context

# -----------------------------------------------------------------------------
# 5. Streamlit UI Tasarımı ve Sekmeler
# -----------------------------------------------------------------------------
st.title("TRADER WORKSTATION: TARAMA")

tab1, tab2 = st.tabs(["Hibrit Tarama", "Düşeni Kıran"])

# ==========================================
# TAB 1: HİBRİT TARAMA SİSTEMİ
# ==========================================
with tab1:
    st.write("### Hibrit İndikatör ve Hacim Taraması")
    col_tf, col_btn = st.columns([3, 1])
    with col_tf:
        selected_tf = st.selectbox("Periyot Seçin:", list(TIMEFRAME_CONFIGS.keys()), index=1, key="tab1_tf")
    with col_btn:
        st.write("##")
        execute_scan = st.button("HİBRİT SİSTEMİ TETİKLE 🚀", key="tab1_btn")

    if "tab1_rows" not in st.session_state: st.session_state.tab1_rows = []
    if "tab1_dfs" not in st.session_state: st.session_state.tab1_dfs = {}

    if execute_scan:
        tf_config = TIMEFRAME_CONFIGS[selected_tf]
        st.session_state.tab1_rows = []
        st.session_state.tab1_dfs = {}
        
        console_placeholder = st.empty()
        progress_bar = st.progress(0)
        
        with st.spinner("TradingView Filtreleri Çalıştırılıyor..."):
            tv_passed_stocks = scan_tradingview_by_timeframe(tf_config)
            
        if not tv_passed_stocks:
            st.warning("TradingView aşamasını geçebilen hisse bulunamadı.")
        else:
            live_logs = [f"[SYSTEM]: TV aşamasını geçen {len(tv_passed_stocks)} hisse için Yahoo denetimi başladı...\n"]
            console_placeholder.code("\n".join(live_logs))
            total_len = len(tv_passed_stocks)
            
            for idx, (symbol, tv_data) in enumerate(tv_passed_stocks.items()):
                progress_bar.progress((idx + 1) / total_len)
                is_matched, v_data, df_target = check_yfinance_volume_condition(symbol, tf_config)
                time.sleep(random.uniform(0.05, 0.15))
                
                if v_data is None:
                    continue
                    
                if is_matched:
                    macd_status = f"🔴" if tv_data['macd'] < 0 else f"🟢"
                    macd_status += f" ({tv_data['macd']:.2f}/{tv_data['signal']:.2f})"
                    tv_url = f"https://www.tradingview.com/chart/?symbol=BIST:{symbol}&interval={tf_config['tv_interval']}"
                    
                    st.session_state.tab1_rows.append({
                        "Hisse": symbol,
                        "Fiyat": round(v_data["price"], 2),
                        "RSI": round(tv_data["rsi"], 1),
                        "MACD Durumu": macd_status,
                        "SMA(20/50/200)": f"{safe_fmt(tv_data['sma20'],'.1f')}/{safe_fmt(tv_data['sma50'],'.1f')}/{safe_fmt(tv_data['sma200'],'.1f')}",
                        "V1": f"{v_data['v1']:,.0f}", "V2": f"{v_data['v2']:,.0f}", "V3": f"{v_data['v3']:,.0f}",
                        "TradingView 🌐": tv_url
                    })
                    st.session_state.tab1_dfs[symbol] = df_target
                    live_logs.append(f"[✓] {symbol:<6} Şartlar Sağlandı!")
                else:
                    live_logs.append(f"[X] {symbol:<6} Hacim Yetersiz.")
                console_placeholder.code("\n".join(live_logs[-10:]))
                
            st.success("Tab 1 Taraması Tamamlandı!")

    if st.session_state.tab1_rows:
        st.write("---")
        st.dataframe(pd.DataFrame(st.session_state.tab1_rows), use_container_width=True, hide_index=True,
                     column_config={"TradingView 🌐": st.column_config.LinkColumn("Grafiğe Git ↗")})
        
        st.write("### 🔬 Grafik İnceleme İstasyonu")
        sel_stock = st.selectbox("Hisseyi seçin:", list(st.session_state.tab1_dfs.keys()), key="tab1_stock")
        if sel_stock:
            st.pyplot(draw_trader_chart(sel_stock, st.session_state.tab1_dfs[sel_stock]))

# ==========================================
# TAB 2: PINE SCRIPT (PIVOT BREAKOUT) SİSTEMİ
# ==========================================
with tab2:
    st.write("### Düşeni Kıran (Trend Kırılımı) Tarama Modülü")
    st.info("Çoklu veri çekimi sunucu tarafında önbelleklenir.")
    
    col_p1, col_p2, col_p3 = st.columns(3)
    left_bars = col_p1.number_input("Sol Pivot Bar Sayısı (leftBars)", min_value=1, value=10)
    right_bars = col_p2.number_input("Sağ Pivot Bar Sayısı (rightBars)", min_value=1, value=2)
    
    st.write("##")
    run_pine_scan = st.button("PINE SCRIPT ALGORİTMASINI TETİKLE 🚀", key="tab2_btn")
    
    if "tab2_rows" not in st.session_state: st.session_state.tab2_rows = []
    
    if run_pine_scan:
        st.session_state.tab2_rows = []
        
        with st.spinner("1. BIST hisse havuzu çekiliyor..."):
            bist_symbols = get_all_bist_symbols()
            
        if not bist_symbols:
            st.error("BIST listesi çekilemedi.")
        else:
            yf_tickers = [f"{s}.IS" for s in bist_symbols]
            
            with st.spinner(f"2. {len(bist_symbols)} Hisse için veriler önbellekten veya Yahoo'dan alınıyor..."):
                df_all = fetch_all_bist_data_cached(yf_tickers)
            
            with st.spinner("3. Algoritma uygulanıyor..."):
                pine_logs = []
                pine_console = st.empty()
                p_bar = st.progress(0)
                
                for idx, symbol in enumerate(bist_symbols):
                    p_bar.progress((idx + 1) / len(bist_symbols))
                    ticker = f"{symbol}.IS"
                    
                    if ticker in df_all.columns.levels[0]:
                        df_symbol = df_all[ticker].dropna(subset=['High', 'Close', 'Open'])
                        
                        is_breakout, context = evaluate_pine_script_logic(df_symbol, left_bars, right_bars)
                        
                        if is_breakout:
                            pine_logs.append(f"[BREAKOUT] {symbol:<6} - Düşen trendi kırdı!")
                            pine_console.code("\n".join(pine_logs[-15:]))
                            
                            tv_url = f"https://www.tradingview.com/chart/?symbol=BIST:{symbol}&interval=D"
                            st.session_state.tab2_rows.append({
                                "Hisse": symbol,
                                "Kapanış Fiyatı (TL)": round(context["price"], 2),
                                "Kırılan Trend Direnci": round(context["trend_val"], 2),
                                "Pivot-1 (Son Zirve)": round(context["p1_price"], 2),
                                "Pivot-2 (Önceki Zirve)": round(context["p2_price"], 2),
                                "TradingView 🌐": tv_url
                            })
                            
            st.success("Pine Script Taraması Tamamlandı!")
            
    if st.session_state.tab2_rows:
        st.write("---")
        st.write("### Düşen Trendi Kıran Hisseler")
        st.dataframe(pd.DataFrame(st.session_state.tab2_rows), use_container_width=True, hide_index=True,
                     column_config={"TradingView 🌐": st.column_config.LinkColumn("Grafiğe Git ↗")})
