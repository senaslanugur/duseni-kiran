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
# TAB 1 - MEVCUT KONFİGÜRASYON (DOKUNULMADI)
# -----------------------------------------------------------------------------
TIMEFRAME_CONFIGS = {
    "4 Saatlik (4H)": {"tv_suffix": "|240", "tv_interval": "240", "yf_interval": "1h", "resample_rule": "4h", "period": "3mo"},
    "1 Günlük (1D)": {"tv_suffix": "", "tv_interval": "D", "yf_interval": "1d", "resample_rule": None, "period": "1y"},
    "1 Haftalık (1W)": {"tv_suffix": "|1W", "tv_interval": "W", "yf_interval": "1wk", "resample_rule": None, "period": "3y"}
}

def safe_fmt(val, fmt=".2f"):
    if val is None or pd.isna(val): return "N/A"
    return f"{val:{fmt}}"

# =============================================================================
# ORTAK VERİ VE TAB 1 FONKSİYONLARI (DOKUNULMADI)
# =============================================================================
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
        "options": {"lang": "en"}, "markets": ["turkey"],
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

def check_yfinance_volume_condition(symbol, tf_config):
    try:
        df = yf.download(tickers=f"{symbol}.IS", period=tf_config["period"], interval=tf_config["yf_interval"], progress=False)
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

def draw_trader_chart(symbol, df_target):
    df = df_target.tail(60).copy() 
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
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(15, 12), sharex=True, gridspec_kw={'height_ratios': [3, 1.2, 1.2, 1.2]})
    fig.suptitle(f"{symbol} | DETAYLI TEKNİK ANALİZ WORKSTATION", fontsize=14, fontweight='bold', color='#d97706')
    ax1.plot(df.index, df['close'], color='#ffffff', label='Kapanış', linewidth=1.5)
    ax1.plot(df.index, df['sma20'], color='#00ffff', label='SMA 20', linestyle='--', linewidth=1)
    ax1.plot(df.index, df['sma50'], color='#ff00ff', label='SMA 50', linestyle='--', linewidth=1)
    ax1.plot(df.index, df['sma200'], color='#ffff00', label='SMA 200', linestyle='-', linewidth=1.2)
    ax1.set_title("FIYAT TRENDI & HAREKETLI ORTALAMALAR", color='#9ca3af', loc='left', fontsize=10)
    ax1.legend(loc='upper left', frameon=False)
    ax1.grid(True, alpha=0.1)
    colors = ['#1f77b4'] * len(df)
    colors[-3], colors[-2], colors[-1] = '#374151', '#6b7280', '#10b981' 
    ax2.bar(df.index, df['volume'], color=colors, width=0.6, alpha=0.85)
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

def get_all_bist_symbols():
    try:
        resp = requests.post("https://scanner.tradingview.com/turkey/scan", json={"filter": [{"left": "type", "operation": "in_range", "right": ["stock"]}], "options": {"lang": "en"}, "markets": ["turkey"], "symbols": {"query": {"types": []}, "tickers": []}, "columns": ["name"], "range": [0, 600]}, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200: return [item["d"][0] for item in resp.json().get("data", [])]
    except: pass
    return []

# =============================================================================
# TAB 2 - TRADER MANTIĞI: 3 YILLIK MAKRO TREND VE HACİM ONAYI
# =============================================================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_macro_bist_data_cached(tickers):
    # Makro görünüm için tam 5 yıllık haftalık mumlar indirilir.
    return yf.download(tickers=tickers, period="5y", interval="1wk", group_by="ticker", threads=True, progress=False)

def evaluate_macro_trader_breakout(df, lookback_bars=200):
    """
    Trader stratejisi: 3-4 Yıllık devasa bir baskının hacimli kırılıp kırılmadığını kontrol eder.
    """
    if df is None or len(df) < lookback_bars + 5: 
        return False, None
    
    highs = df['High'].values
    closes = df['Close'].values
    opens = df['Open'].values
    volumes = df['Volume'].values
    
    curr_idx = len(highs) - 1
    prev_idx = curr_idx - 1
    
    # 1. Ana Tepeyi (Tarihi Zirveyi) Bul
    start_search = max(0, curr_idx - lookback_bars)
    u_start_b = start_search + np.argmax(highs[start_search:curr_idx])
    u_start_p = highs[u_start_b]
    
    # 2. En dıştaki teğet noktasını (Sert Satış Direncini) Bul
    max_u_slope = -np.inf
    u_sec_b = -1
    u_sec_p = -1
    
    for i in range(u_start_b + 1, curr_idx):
        slope = (highs[i] - u_start_p) / (i - u_start_b)
        if slope < 0 and slope > max_u_slope:
            max_u_slope = slope
            u_sec_b = i
            u_sec_p = highs[i]
            
    if u_sec_b == -1: 
        return False, None
        
    # 3. Kırılım Çizgisini (Direnci) Hesapla
    prev_trendline = u_start_p + max_u_slope * (prev_idx - u_start_b)
    curr_trendline = u_start_p + max_u_slope * (curr_idx - u_start_b)
    
    # ---------------------------------------------------------
    # 4. TRADER KOŞULLARI (FİYAT + HACİM)
    # ---------------------------------------------------------
    # A. Fiyat Kırılımı: Önceki hafta altında, bu hafta üstünde mi?
    line_crossed = (closes[prev_idx] <= prev_trendline) and (closes[curr_idx] > curr_trendline)
    
    # B. Yeşil/Alıcılı Mum: Kapanış açılışın üzerinde mi? (Satış yiyip fitil bırakmamış olmalı)
    is_green_candle = closes[curr_idx] > opens[curr_idx]
    
    # C. Hacim Şoku (Smart Money Onayı): Son 1 ayın (4 hafta) ortalama hacmi
    avg_vol_1m = np.mean(volumes[curr_idx-4 : curr_idx])
    curr_vol = volumes[curr_idx]
    
    # Hacim, son 1 ayın ortalamasından en az %50 fazla olmalı (Sıfıra bölünme hatasını engelle)
    is_volume_backed = False
    vol_increase_pct = 0
    if avg_vol_1m > 0:
        is_volume_backed = curr_vol > (avg_vol_1m * 1.5)
        vol_increase_pct = ((curr_vol / avg_vol_1m) - 1) * 100

    pro_breakout = line_crossed and is_green_candle and is_volume_backed
    
    if pro_breakout:
        return True, {
            "price": closes[curr_idx],
            "trend_val": curr_trendline,
            "u_start_p": u_start_p,
            "vol_increase": vol_increase_pct
        }
    return False, None

# =============================================================================
# UI RENDER MİMARİSİ
# =============================================================================
st.title("TRADER WORKSTATION")
tab1, tab2 = st.tabs(["HİBRİT TARAMA", "MAKRO TREND KIRILIMI (3 YIL + HACİM)"])

# ------------------------- TAB 1 -------------------------
with tab1:
    col_tf, col_btn = st.columns([3, 1])
    with col_tf: selected_tf = st.selectbox("Zaman Periyodu:", list(TIMEFRAME_CONFIGS.keys()), index=1)
    with col_btn: st.write("##"); execute_scan = st.button("TARAMAYI BAŞLAT")

    if "final_rows" not in st.session_state: st.session_state.final_rows = []
    if "stored_dfs" not in st.session_state: st.session_state.stored_dfs = {}
    if "last_tf" not in st.session_state: st.session_state.last_tf = ""

    if execute_scan:
        tf_config = TIMEFRAME_CONFIGS[selected_tf]
        st.session_state.last_tf = selected_tf
        st.session_state.final_rows = []
        st.session_state.stored_dfs = {}
        
        st.write("### SİSTEM LOG KONSOLU")
        console_placeholder = st.empty()
        progress_bar = st.progress(0)
        
        with st.spinner("TradingView API ile iletişim kuruluyor..."):
            tv_passed_stocks = scan_tradingview_by_timeframe(tf_config)
            
        if not tv_passed_stocks:
            st.markdown("<div style='color:#f59e0b; font-family:Inter; font-weight:600;'>[SİSTEM UYARISI] Belirtilen kriterlerde hisse bulunamadı.</div>", unsafe_allow_html=True)
        else:
            live_logs = [f"[SYSTEM]: İlk aşamayı geçen {len(tv_passed_stocks)} hisse için hacim onayı başlatıldı...\n"]
            console_placeholder.code("\n".join(live_logs))
            total_len = len(tv_passed_stocks)
            
            for idx, (symbol, tv_data) in enumerate(tv_passed_stocks.items()):
                progress_bar.progress((idx + 1) / total_len)
                is_matched, v_data, df_target = check_yfinance_volume_condition(symbol, tf_config)
                time.sleep(random.uniform(0.05, 0.15)) 
                
                if v_data is None:
                    live_logs.append(f"[ERR]  {symbol:<6} : Veri bağlantısı kurulamadı.")
                    console_placeholder.code("\n".join(live_logs[-15:])); continue
                    
                v1_f, v2_f, v3_f = f"{v_data['v1']:,.0f}", f"{v_data['v2']:,.0f}", f"{v_data['v3']:,.0f}"
        
                if is_matched:
                    live_logs.append(f"[OK]   {symbol:<6} : V1:{v1_f} < V2:{v2_f} < V3:{v3_f} (Hacim Onaylandı)")
                    macd_val, sig_val = tv_data['macd'], tv_data['signal']
                    macd_status = f"NEGATIF BOLGE ({macd_val:.2f}/{sig_val:.2f})" if macd_val is not None and macd_val < 0 else f"POZITIF BOLGE ({macd_val:.2f}/{sig_val:.2f})"
                    tv_url = f"https://www.tradingview.com/chart/?symbol=BIST:{symbol}&interval={tf_config['tv_interval']}"
                    
                    st.session_state.final_rows.append({"Hisse": symbol, "Fiyat (TL)": round(v_data["price"], 2), "RSI (50+)": round(tv_data["rsi"], 1), "MACD Durumu": macd_status, "SMA (20/50/200)": f"{safe_fmt(tv_data['sma20'], '.1f')} / {safe_fmt(tv_data['sma50'], '.1f')} / {safe_fmt(tv_data['sma200'], '.1f')}", "V1 (T-2)": v1_f, "V2 (T-1)": v2_f, "V3 (Güncel)": v3_f, "Bağlantı": tv_url})
                    st.session_state.stored_dfs[symbol] = df_target
                else: live_logs.append(f"[FAIL] {symbol:<6} : V1:{v1_f} -> V2:{v2_f} -> V3:{v3_f} (Koşul Sağlanmadı)")
                console_placeholder.code("\n".join(live_logs[-15:]))
                
            st.markdown("<div style='color:#10b981; font-family:Inter; font-weight:600;'>[SİSTEM BİLGİSİ] Tarama işlemi başarıyla tamamlandı.</div>", unsafe_allow_html=True)

    if st.session_state.final_rows:
        st.write("---"); st.write(f"### ONAYLANMIŞ HİSSELER ({st.session_state.last_tf})")
        st.dataframe(pd.DataFrame(st.session_state.final_rows), use_container_width=True, hide_index=True, column_config={"Hisse": st.column_config.TextColumn("Hisse"), "Bağlantı": st.column_config.LinkColumn("TradingView", display_text="Grafiği Aç")})
        st.write("---"); st.write("### GRAFİK İNCELEME İSTASYONU")
        selected_stock_to_plot = st.selectbox("Detaylı inceleme için hisse seçin:", list(st.session_state.stored_dfs.keys()))
        if selected_stock_to_plot: st.pyplot(draw_trader_chart(selected_stock_to_plot, st.session_state.stored_dfs[selected_stock_to_plot]))
    elif st.session_state.last_tf:
        st.write("---"); st.markdown(f"<div style='color:#9ca3af; font-family:Inter; font-weight:600;'>[SİSTEM BİLGİSİ] {st.session_state.last_tf} periyodunda belirtilen hacim ve indikatör koşullarını sağlayan hisse bulunamadı.</div>", unsafe_allow_html=True)

# ------------------------- TAB 2 -------------------------
with tab2:
    st.write("### HACİM ONAYLI MAKRO TREND KIRILIM STRATEJİSİ")
    
    st.markdown("""
    <div style='background-color:#111827; padding:15px; border-left:4px solid #10b981; margin-bottom:20px;'>
        <div style='color:#e5e7eb; font-weight:600; font-size:14px; margin-bottom:5px;'>Kurumsal Para (Smart Money) Avcısı Devrede:</div>
        <div style='color:#9ca3af; font-size:13px;'>Bu strateji günlük tuzakları görmezden gelir. Tüm BIST havuzunda son 5 YILLIK HAFTALIK grafikleri tarar.</div>
        <div style='color:#10b981; font-family:JetBrains Mono; font-size:12px; margin-top:8px;'>
            [+] Koşul 1: 3-4 yıllık devasa düşen trend çizgisinin yukarı kırılması.<br>
            [+] Koşul 2: Kırılım mumunun yeşil (Kapanış > Açılış) ve güçlü olması.<br>
            [+] Koşul 3: Hacmin son 1 ayın (4 hafta) ortalamasından en az %50 DAHA YÜKSEK olması.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    run_macro_scan = st.button("TÜM PİYASAYI TARA (HAFTALIK)", key="tab2_btn")
    
    if "tab2_rows" not in st.session_state: st.session_state.tab2_rows = []
    
    if run_macro_scan:
        st.session_state.tab2_rows = []
        
        with st.spinner("BIST Sembol verileri senkronize ediliyor..."):
            bist_symbols = get_all_bist_symbols()
            
        if not bist_symbols:
            st.markdown("<div style='color:#ef4444; font-family:Inter; font-weight:600;'>[SİSTEM HATASI] Bağlantı hatası: BIST listesi alınamadı.</div>", unsafe_allow_html=True)
        else:
            yf_tickers = [f"{s}.IS" for s in bist_symbols]
            
            with st.spinner(f"Makro veri havuzu oluşturuluyor ({len(bist_symbols)} hisse, 5 Yıllık Haftalık Veri)..."):
                # Sadece Haftalık ve 5 Yıllık Veri Çekilir
                df_all = fetch_macro_bist_data_cached(tickers=yf_tickers)
            
            with st.spinner("Fiyat hareketi ve hacim patlaması taranıyor..."):
                pine_logs = []
                pine_console = st.empty()
                p_bar = st.progress(0)
                
                for idx, symbol in enumerate(bist_symbols):
                    p_bar.progress((idx + 1) / len(bist_symbols))
                    ticker = f"{symbol}.IS"
                    
                    if ticker in df_all.columns.levels[0]:
                        # Hacim verisi eklendiği için Volume sütununu da düşürmüyoruz
                        df_symbol = df_all[ticker].dropna(subset=['High', 'Close', 'Open', 'Volume'])
                        
                        is_breakout, context = evaluate_macro_trader_breakout(df_symbol)
                        
                        if is_breakout:
                            pine_logs.append(f"[🔥 DEV KIRILIM] {symbol:<6} : Hacim Oranı +%{context['vol_increase']:.0f}!")
                            pine_console.code("\n".join(pine_logs[-15:]))
                            
                            tv_url = f"https://www.tradingview.com/chart/?symbol=BIST:{symbol}&interval=W"
                            st.session_state.tab2_rows.append({
                                "Hisse": symbol,
                                "Kapanış": round(context["price"], 2),
                                "Kırılan Direnç": round(context["trend_val"], 2),
                                "Tarihi Zirve": round(context["u_start_p"], 2),
                                "Hacim Patlaması": f"+%{context['vol_increase']:.1f}",
                                "Bağlantı": tv_url
                            })
                            
            st.markdown("<div style='color:#10b981; font-family:Inter; font-weight:600;'>[SİSTEM BİLGİSİ] Strateji taraması tamamlandı.</div>", unsafe_allow_html=True)
            
    if st.session_state.tab2_rows:
        st.write("---")
        st.write("### 🏆 HACİMLİ MAKRO KIRILIMI ONAYLANAN HİSSELER")
        st.dataframe(pd.DataFrame(st.session_state.tab2_rows), use_container_width=True, hide_index=True,
                     column_config={
                         "Bağlantı": st.column_config.LinkColumn("TradingView (Haftalık)", display_text="Grafiği Aç")
                     })
