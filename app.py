# ------------------------- TAB 4 -------------------------
with tab4:
    st.write("### KESİŞİM MATRİSİ (HACİM + FIBONACCI)")
    col_mkt4, col_btn4 = st.columns()
    with col_mkt4: t4_selected_mkt = st.selectbox("Piyasa Seçin:", list(MARKET_CONFIGS.keys()), key="t4_mkt")
    with col_btn4: st.write("##"); run_perfect_scan = st.button("ALGORİTMAYI ATEŞLE", key="t4_btn")
        
    if "tab4_rows" not in st.session_state: 
        st.session_state.tab4_rows = []
    
    if run_perfect_scan:
        mkt_config = MARKET_CONFIGS[t4_selected_mkt]
        st.session_state.tab4_rows = []
        
        with st.spinner(f"{t4_selected_mkt} Sembol verileri senkronize ediliyor..."):
            market_symbols = get_all_market_symbols(mkt_config)
            
        if not market_symbols:
            st.markdown("<div style='color:#ef4444; font-family:Inter; font-weight:600;'>[SİSTEM HATASI] Bağlantı hatası: Liste alınamadı.</div>", unsafe_allow_html=True)
        else:
            yf_tickers = [f"{s.replace('.', '-')}{mkt_config['yf_suffix']}" for s in market_symbols]
            
            with st.spinner("Makro Veri (5 Yıllık) ve Mikro Veri (1 Yıllık) Çoklu Havuzu Oluşturuluyor..."):
                df_weekly_all = fetch_macro_data_cached(tickers=yf_tickers)
                df_daily_all = fetch_fib_data_cached(tickers=yf_tickers)
                
            with st.spinner("Kusursuz Kesişim Matrisi (Hacim Patlaması + Matematiksel Döngü) taranıyor..."):
                p_bar = st.progress(0)
                for idx, symbol in enumerate(market_symbols):
                    p_bar.progress((idx + 1) / len(market_symbols))
                    yf_ticker_key = f"{symbol.replace('.', '-')}{mkt_config['yf_suffix']}"
                    
                    if (yf_ticker_key in df_weekly_all.columns.levels[0]) and (yf_ticker_key in df_daily_all.columns.levels[0]):
                        df_weekly = df_weekly_all[yf_ticker_key].dropna(subset=['High', 'Close', 'Open', 'Volume'])
                        df_daily = df_daily_all[yf_ticker_key].dropna(subset=['High', 'Low', 'Close', 'Open'])
                        
                        is_macro_break, macro_ctx = evaluate_macro_trader_breakout(df_weekly)
                        is_fib_setup, fib_ctx = evaluate_auto_fibonacci(df_daily)
                        
                        if is_macro_break and is_fib_setup:
                            tv_url = f"https://tradingview.com{mkt_config['tv_prefix']}{symbol}&interval=D"
                            st.session_state.tab4_rows.append({
                                "Hisse": symbol,
                                "Güncel Fiyat": round(fib_ctx["price"], 2),
                                "Kırılan Makro Direnç": round(macro_ctx["trend_val"], 2),
                                "Hacim Artışı": f"+%{macro_ctx['vol_increase']:.1f}",
                                "Fibonacci Döngüsü": fib_ctx["phase"],
                                "Uzay Hedefi (1.618)": round(fib_ctx["fib_target"], 2),
                                "Bağlantı": tv_url
                            })
                            
            st.markdown("<div style='color:#f59e0b; font-family:Inter; font-weight:600;'>[SİSTEM BİLGİSİ] Kesişim matrisi taraması tamamlandı.</div>", unsafe_allow_html=True)

    # Tarama sonuçlarının güvenli kontrolü ve ekrana basılması
    if st.session_state.tab4_rows:
        perfect_df = pd.DataFrame(st.session_state.tab4_rows)
        
        # DataFrame'in boş olup olmadığının matematiksel doğrulaması (Kritik Hata Çözümü)
        if not perfect_df.empty:
            st.write("---")
            st.write(f"### 🔥 HEM HACİM HEM FIBONACCI ONAYLI KUSURSUZ KESİŞİM HİSSELERİ ({t4_selected_mkt})")
            
            # Sıralama artık güvenle çalışacaktır
            perfect_df = perfect_df.sort_values(by="Fibonacci Döngüsü")
            
            st.dataframe(
                perfect_df, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Hisse": st.column_config.TextColumn("Sembol Sembolü", help="Kesişim sağlayan varlık"),
                    "Güncel Fiyat": st.column_config.NumberColumn("Son Fiyat", format="%.2f"),
                    "Kırılan Makro Direnç": st.column_config.NumberColumn("Kırılan Yapı", format="%.2f", help="Haftalık grafikte kırılan makro direnç"),
                    "Hacim Artışı": st.column_config.TextColumn("Haftalık Hacim Patlaması", help="Ortalamaya göre hacim artış oranı"),
                    "Fibonacci Döngüsü": st.column_config.TextColumn("Fibonacci Döngü Durumu", width="medium"),
                    "Uzay Hedefi (1.618)": st.column_config.NumberColumn("Matematiksel Hedef (1.618)", format="%.2f", help="Zirve aşımı sonrası teorik ana hedef"),
                    "Bağlantı": st.column_config.LinkColumn("TradingView (Günlük)", display_text="Sinyali İncele")
                }
            )
        else:
            st.info("Seçilen piyasada kriterlere uyan bir kesişim hissesi bulunamadı.")
    elif run_perfect_scan: # Butona basılmış ama liste hiç dolmamışsa
        st.info("Seçilen piyasada hem haftalık hacimli kırılım gösteren hem de günlük otonom Fibonacci yapısında olan bir kesişim hissesi bulunamadı.")
