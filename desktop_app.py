import customtkinter as ctk
import subprocess
import threading
import os
import re
import time

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "config.py"
HISTORY_FILE = "trade_history.txt"

class AlgoBotApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AlgoBot AI - Панель управления (Фьючерсы)")
        self.geometry("1000x700")
        
        self.bot_process = None
        self.read_config()
        
        # --- ЛЕВАЯ ПАНЕЛЬ (Настройки со скроллом) ---
        self.sidebar = ctk.CTkScrollableFrame(self, width=290, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        
        self.logo = ctk.CTkLabel(self.sidebar, text="⚙️ НАСТРОЙКИ БОТА", font=ctk.CTkFont(size=18, weight="bold"))
        self.logo.pack(pady=20, padx=20)
        
        # Режим торговли
        self.lbl_mode = ctk.CTkLabel(self.sidebar, text="Тип торговли:")
        self.lbl_mode.pack(pady=(5, 0), padx=20, anchor="w")
        self.seg_mode = ctk.CTkSegmentedButton(self.sidebar, values=["NORMAL", "SCALPING"], command=self.change_mode)
        self.seg_mode.pack(pady=5, padx=20, fill="x")
        self.seg_mode.set(self.current_mode)
        
        # Режим Риска
        self.lbl_risk = ctk.CTkLabel(self.sidebar, text="Риск-менеджмент:")
        self.lbl_risk.pack(pady=(15, 0), padx=20, anchor="w")
        self.seg_risk = ctk.CTkSegmentedButton(self.sidebar, values=["ЭКОНОМ", "БАЛАНС", "АГРЕССИВ"], command=self.change_risk)
        self.seg_risk.pack(pady=5, padx=20, fill="x")
        
        # Устанавливаем текущий риск
        risk_map = {"CONSERVATIVE": "ЭКОНОМ", "BALANCED": "БАЛАНС", "AGGRESSIVE": "АГРЕССИВ"}
        self.seg_risk.set(risk_map.get(self.current_risk, "БАЛАНС"))
        
        # Объем сделки
        self.lbl_trade_size = ctk.CTkLabel(self.sidebar, text="Маржа на 1 сделку ($):")
        self.lbl_trade_size.pack(pady=(15, 0), padx=20, anchor="w")
        self.entry_trade_size = ctk.CTkEntry(self.sidebar)
        self.entry_trade_size.insert(0, self.current_trade_size)
        self.entry_trade_size.pack(pady=5, padx=20, fill="x")
        
        # Плечо
        self.lbl_lev = ctk.CTkLabel(self.sidebar, text="Кредитное плечо (x):")
        self.lbl_lev.pack(pady=(5, 0), padx=20, anchor="w")
        self.entry_lev = ctk.CTkEntry(self.sidebar)
        self.entry_lev.insert(0, self.current_lev)
        self.entry_lev.pack(pady=5, padx=20, fill="x")
        
        # Общий лимит
        self.lbl_cap = ctk.CTkLabel(self.sidebar, text="Торговый лимит ($):")
        self.lbl_cap.pack(pady=(5, 0), padx=20, anchor="w")
        self.entry_cap = ctk.CTkEntry(self.sidebar)
        self.entry_cap.insert(0, self.current_cap)
        self.entry_cap.pack(pady=5, padx=20, fill="x")
        
        # Стоп-лосс
        self.lbl_sl = ctk.CTkLabel(self.sidebar, text="Stop-Loss (%):")
        self.lbl_sl.pack(pady=(10, 0), padx=20, anchor="w")
        self.entry_sl = ctk.CTkEntry(self.sidebar)
        self.entry_sl.insert(0, str(float(self.current_sl) * 100))
        self.entry_sl.pack(pady=5, padx=20, fill="x")
        
        # Тейк-профит
        self.lbl_tp = ctk.CTkLabel(self.sidebar, text="Take-Profit (%):")
        self.lbl_tp.pack(pady=(5, 0), padx=20, anchor="w")
        self.entry_tp = ctk.CTkEntry(self.sidebar)
        self.entry_tp.insert(0, str(float(self.current_tp) * 100))
        self.entry_tp.pack(pady=5, padx=20, fill="x")
        
        # --- PRO FEATURES ---
        self.pro_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.pro_frame.pack(fill="x", padx=20, pady=10)
        
        self.chk_atr = ctk.CTkCheckBox(self.pro_frame, text="Динамический TP/SL (ATR)")
        self.chk_atr.pack(anchor="w", pady=2)
        if self.current_use_atr: self.chk_atr.select()
        
        self.chk_trail = ctk.CTkCheckBox(self.pro_frame, text="Трейлинг-Стоп")
        self.chk_trail.pack(anchor="w", pady=2)
        if self.current_use_trail: self.chk_trail.select()
        
        self.chk_comp = ctk.CTkCheckBox(self.pro_frame, text="Авто-Реинвестирование")
        self.chk_comp.pack(anchor="w", pady=2)
        if self.current_use_comp: self.chk_comp.select()
        
        self.lbl_comp_pct = ctk.CTkLabel(self.pro_frame, text="% от баланса:")
        self.lbl_comp_pct.pack(anchor="w")
        self.entry_comp_pct = ctk.CTkEntry(self.pro_frame)
        self.entry_comp_pct.insert(0, str(self.current_comp_pct))
        self.entry_comp_pct.pack(fill="x", pady=2)
        
        # Кнопка сохранения
        self.btn_save = ctk.CTkButton(self.sidebar, text="💾 Сохранить", command=self.save_config, fg_color="gray")
        self.btn_save.pack(pady=5, padx=20, fill="x")
        
        # Кнопка обучения ИИ
        self.btn_train = ctk.CTkButton(self.sidebar, text="🧠 Переобучить ИИ", command=self.train_ai, fg_color="#E67E22", hover_color="#D35400")
        self.btn_train.pack(pady=(5, 25), padx=20, fill="x")
        
        # --- ПРАВАЯ ПАНЕЛЬ (Позиции) ---
        self.right_sidebar = ctk.CTkFrame(self, width=250)
        self.right_sidebar.pack(side="right", fill="y", padx=(0, 10), pady=10)
        
        lbl_pos_title = ctk.CTkLabel(self.right_sidebar, text="Текущие Позиции", font=ctk.CTkFont(size=16, weight="bold"))
        lbl_pos_title.pack(pady=10)
        
        self.pos_scroll = ctk.CTkScrollableFrame(self.right_sidebar, width=230)
        self.pos_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.btn_refresh_pos = ctk.CTkButton(self.right_sidebar, text="🔄 Обновить", command=self.refresh_positions, fg_color="#3498DB", hover_color="#2980B9")
        self.btn_refresh_pos.pack(pady=10, padx=10, fill="x")

        # --- ЦЕНТРАЛЬНАЯ ПАНЕЛЬ (Логи и Управление) ---
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        # Баланс
        self.top_bar = ctk.CTkFrame(self.main_frame)
        self.top_bar.pack(fill="x", pady=5, padx=5)
        
        self.lbl_balance = ctk.CTkLabel(self.top_bar, text="Баланс Фьючерсов: Загрузка...", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_balance.pack(side="left", padx=10)
        
        self.btn_refresh_bal = ctk.CTkButton(self.top_bar, text="🔄 Обновить", width=100, command=self.fetch_balance)
        self.btn_refresh_bal.pack(side="right", padx=10, pady=5)
        
        # Статус
        self.lbl_status = ctk.CTkLabel(self.main_frame, text="СТАТУС: ОСТАНОВЛЕН", font=ctk.CTkFont(size=18, weight="bold"), text_color="red")
        self.lbl_status.pack(pady=10)
        
        # Кнопки управления
        self.controls = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.controls.pack(fill="x", pady=5)
        
        self.btn_start = ctk.CTkButton(self.controls, text="▶️ ЗАПУСТИТЬ ТОРГОВЛЮ", command=self.start_bot, fg_color="green", hover_color="darkgreen")
        self.btn_start.pack(side="left", expand=True, padx=5)
        
        self.btn_graceful = ctk.CTkButton(self.controls, text="🏁 Доработать и выключить", command=self.graceful_stop, fg_color="#F39C12", hover_color="#D68910", state="disabled")
        self.btn_graceful.pack(side="left", expand=True, padx=5)
        
        self.btn_stop = ctk.CTkButton(self.controls, text="⏹ ЭКСТРЕННЫЙ СТОП", command=self.stop_bot, fg_color="red", hover_color="darkred", state="disabled")
        self.btn_stop.pack(side="left", expand=True, padx=5)
        
        # Вкладки (Логи / История / Аналитика)
        self.tabs = ctk.CTkTabview(self.main_frame)
        self.tabs.pack(fill="both", expand=True, padx=5, pady=5)
        self.tabs.add("Консоль (Live)")
        self.tabs.add("История Сделок")
        self.tabs.add("📊 Аналитика (PRO)")
        
        # Консоль
        self.console_tab = self.tabs.tab("Консоль (Live)")
        
        # Панель быстрых действий консоли
        self.console_bar = ctk.CTkFrame(self.console_tab, fg_color="transparent")
        self.console_bar.pack(fill="x", pady=(0, 5))
        
        self.btn_copy_logs = ctk.CTkButton(self.console_bar, text="📋 Скопировать всё", width=140, height=26, command=self._copy_all_console)
        self.btn_copy_logs.pack(side="left", padx=5)
        
        self.btn_clear_logs = ctk.CTkButton(self.console_bar, text="🧹 Очистить", width=90, height=26, fg_color="#555", hover_color="#333", command=self._clear_console)
        self.btn_clear_logs.pack(side="left", padx=5)
        
        self.console = ctk.CTkTextbox(self.console_tab, font=("Consolas", 12))
        self.console.pack(fill="both", expand=True)
        
        # Контекстное меню ПКМ для консоли
        import tkinter as tk
        self.console_menu = tk.Menu(self, tearoff=0)
        self.console_menu.add_command(label="Копировать (Ctrl+C)", command=self._copy_console_selection)
        self.console_menu.add_command(label="Выделить всё (Ctrl+A)", command=self._select_all_console)
        self.console_menu.add_separator()
        self.console_menu.add_command(label="Очистить", command=self._clear_console)
        
        def _show_console_menu(event):
            try:
                self.console_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.console_menu.grab_release()
        self.console.bind("<Button-3>", _show_console_menu)
        
        # Блокируем клавиатурный ввод в консоль, но оставляем выделение и горячие клавиши
        def _block_typing(event):
            # Ctrl+C, Ctrl+A, Ctrl+Insert
            if (event.state & 4) and event.keysym.lower() in ['c', 'a', 'insert']:
                return None
            # Навигация
            if event.keysym in ['Up', 'Down', 'Left', 'Right', 'Prior', 'Next', 'Home', 'End']:
                return None
            return "break"
        self.console.bind("<Key>", _block_typing)
        
        # История
        self.history_tab = self.tabs.tab("История Сделок")
        self.history_bar = ctk.CTkFrame(self.history_tab, fg_color="transparent")
        self.history_bar.pack(fill="x", pady=(0, 5))
        self.btn_copy_hist = ctk.CTkButton(self.history_bar, text="📋 Скопировать историю", width=160, height=26, command=self._copy_all_history)
        self.btn_copy_hist.pack(side="left", padx=5)
        
        self.history_txt = ctk.CTkTextbox(self.history_tab, font=("Consolas", 12))
        self.history_txt.pack(fill="both", expand=True)
        self.history_txt.bind("<Key>", _block_typing)
        
        # Аналитика
        self.analytics_frame = ctk.CTkFrame(self.tabs.tab("📊 Аналитика (PRO)"), fg_color="transparent")
        self.analytics_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.lbl_stat_trades = ctk.CTkLabel(self.analytics_frame, text="Всего сделок: 0", font=("Consolas", 16))
        self.lbl_stat_trades.pack(anchor="w", pady=5)
        
        self.lbl_stat_winrate = ctk.CTkLabel(self.analytics_frame, text="Win-Rate: 0%", font=("Consolas", 16, "bold"))
        self.lbl_stat_winrate.pack(anchor="w", pady=5)
        
        self.lbl_stat_pnl = ctk.CTkLabel(self.analytics_frame, text="Общий PnL: $0.00", font=("Consolas", 16, "bold"))
        self.lbl_stat_pnl.pack(anchor="w", pady=5)
        
        self.btn_refresh_analytics = ctk.CTkButton(self.analytics_frame, text="🔄 Обновить статистику", command=self.update_analytics)
        self.btn_refresh_analytics.pack(anchor="w", pady=15)
        
        self.update_history_loop()
        self.update_analytics()
        threading.Thread(target=self.fetch_balance, daemon=True).start()
        
        # Запускаем авто-обновление позиций
        self.update_positions_loop()

    def update_positions_loop(self):
        self.refresh_positions()
        # Обновляем позиции каждые 15 секунд автоматически
        self.after(15000, self.update_positions_loop)

    def fetch_balance(self):
        try:
            self.lbl_balance.configure(text="Баланс Фьючерсов: Загрузка...")
            from data_fetcher import DataFetcher
            from config import API_KEY, API_SECRET, USE_TESTNET
            fetcher = DataFetcher(use_testnet=USE_TESTNET, api_key=API_KEY, api_secret=API_SECRET)
            balance = fetcher.exchange.fetch_balance()
            usdt = balance['total'].get('USDT', 0.0)
            self.lbl_balance.configure(text=f"Баланс Фьючерсов: {usdt:.2f} USDT")
        except Exception as e:
            self.lbl_balance.configure(text=f"Ошибка загрузки баланса")
            self.log_message(f"[ОШИБКА АПИ] Не удалось получить баланс: {e}")

    def refresh_positions(self):
        for widget in self.pos_scroll.winfo_children():
            widget.destroy()
        lbl_loading = ctk.CTkLabel(self.pos_scroll, text="Обновление...")
        lbl_loading.pack(pady=10)
        threading.Thread(target=self._fetch_and_render_positions, daemon=True).start()

    def _fetch_and_render_positions(self):
        try:
            from data_fetcher import DataFetcher
            from config import API_KEY, API_SECRET, USE_TESTNET
            fetcher = DataFetcher(use_testnet=USE_TESTNET, api_key=API_KEY, api_secret=API_SECRET)
            positions = fetcher.exchange.fetch_positions()
            
            active_pos = []
            for pos in positions:
                contracts = float(pos.get('contracts', 0))
                if contracts > 0:
                    symbol = pos['symbol']
                    side = pos['side']
                    entry = float(pos['entryPrice'])
                    unrealized_pnl = float(pos.get('unrealizedPnl', 0))
                    
                    leverage = float(pos.get('info', {}).get('leverage', 1))
                    
                    margin = (entry * contracts) / leverage if leverage else (entry * contracts)
                    
                    roe_pct = (unrealized_pnl / margin) * 100 if margin > 0 else 0.0
                    
                    sl, tp = "Нет", "Нет"
                    clean_sym = symbol.split(':')[0]
                    
                    try:
                        import json, os
                        if os.path.exists('live_state.json'):
                            with open('live_state.json', 'r', encoding='utf-8') as f:
                                st = json.load(f)
                                match_key = clean_sym if clean_sym in st else (symbol if symbol in st else None)
                                if match_key:
                                    sl = str(st[match_key].get('sl_price', sl))
                                    tp = str(st[match_key].get('tp_price', tp))
                    except Exception:
                        pass
                        
                    market_pnl = unrealized_pnl
                    try:
                        ticker = fetcher.exchange.fetch_ticker(symbol)
                        bid = float(ticker.get('bid', 0))
                        ask = float(ticker.get('ask', 0))
                        if bid > 0 and ask > 0:
                            if side.upper() == 'LONG':
                                market_pnl = (bid - entry) * contracts
                            else:
                                market_pnl = (entry - ask) * contracts
                    except Exception:
                        pass
                    
                    active_pos.append({
                        'symbol': symbol,
                        'side': side.upper(),
                        'entry': entry,
                        'pnl': unrealized_pnl,
                        'market_pnl': market_pnl,
                        'roe_pct': roe_pct,
                        'sl': sl,
                        'tp': tp,
                        'contracts': contracts
                    })
            self.after(0, lambda pos=active_pos: self._render_positions(pos))
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda err=err_msg: self._render_positions_error(err))

    def _render_positions(self, active_pos):
        for widget in self.pos_scroll.winfo_children():
            widget.destroy()
            
        if not active_pos:
            lbl = ctk.CTkLabel(self.pos_scroll, text="Нет открытых позиций", text_color="gray")
            lbl.pack(pady=20)
            return
            
        for p in active_pos:
            frame = ctk.CTkFrame(self.pos_scroll, fg_color="#2C3E50", corner_radius=8)
            frame.pack(fill="x", pady=5, padx=2)
            
            color = "green" if p['side'] == "LONG" else "red"
            clean_title = p['symbol'].split(':')[0]
            lbl_sym = ctk.CTkLabel(frame, text=f"{clean_title} [{p['side']}]", font=ctk.CTkFont(weight="bold"), text_color=color)
            lbl_sym.pack(anchor="w", padx=5, pady=(5,0))
            
            lbl_info = ctk.CTkLabel(frame, text=f"Вход: {p['entry']:.4f}\nTP: {p['tp']} | SL: {p['sl']}", justify="left")
            lbl_info.pack(anchor="w", padx=5)
            
            pnl_color = "lightgreen" if p['pnl'] >= 0 else "#E74C3C"
            lbl_pnl = ctk.CTkLabel(frame, text=f"PnL (Биржа): {p['pnl']:.2f} USDT ({p['roe_pct']:+.2f}%)", text_color=pnl_color, font=ctk.CTkFont(weight="bold"))
            lbl_pnl.pack(anchor="w", padx=5, pady=(0,0))
            
            mpnl_color = "lightgreen" if p['market_pnl'] >= 0 else "#E74C3C"
            lbl_mpnl = ctk.CTkLabel(frame, text=f"При закрытии сейчас: {p['market_pnl']:.2f} USDT", text_color=mpnl_color, font=ctk.CTkFont(size=11))
            lbl_mpnl.pack(anchor="w", padx=5, pady=(0,5))
            
            btn_close = ctk.CTkButton(frame, text="❌ Закрыть", fg_color="darkred", hover_color="red", height=24,
                                      command=lambda sym=p['symbol'], s=p['side'], c=p['contracts']: self.close_position_manual(sym, s, c))
            btn_close.pack(fill="x", padx=5, pady=5)
            
    def _render_positions_error(self, err):
        for widget in self.pos_scroll.winfo_children():
            widget.destroy()
        lbl = ctk.CTkLabel(self.pos_scroll, text=f"Ошибка:\n{err}", text_color="red", wraplength=200)
        lbl.pack(pady=10)
        
    def close_position_manual(self, symbol, side, contracts):
        def _close():
            try:
                from data_fetcher import DataFetcher
                from config import API_KEY, API_SECRET, USE_TESTNET
                fetcher = DataFetcher(use_testnet=USE_TESTNET, api_key=API_KEY, api_secret=API_SECRET)
                close_side = "sell" if side.upper() == "LONG" else "buy"
                self.log_message(f"🔒 Ручное закрытие позиции {symbol}...")
                
                try:
                    fetcher.exchange.cancel_all_orders(symbol)
                except:
                    pass
                
                fetcher.exchange.create_market_order(symbol, close_side, contracts, params={'reduceOnly': True})
                self.log_message(f"✅ Позиция {symbol} успешно закрыта вручную!")
                
                # Обновляем позиции и баланс сразу после закрытия
                self.after(2000, self.refresh_positions)
                self.after(2000, self.fetch_balance)
            except Exception as e:
                self.log_message(f"[ОШИБКА] Не удалось закрыть позицию {symbol}: {e}")
                
        threading.Thread(target=_close, daemon=True).start()

    def read_config(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                content = f.read()
                
            mode_match = re.search(r'TRADING_MODE\s*=\s*"([^"]+)"', content)
            self.current_mode = mode_match.group(1) if mode_match else "SCALPING"
            
            risk_match = re.search(r'RISK_MODE\s*=\s*"([^"]+)"', content)
            self.current_risk = risk_match.group(1) if risk_match else "BALANCED"
            
            self.current_trade_size = re.search(r'TRADE_SIZE_USDT\s*=\s*([0-9.]+)', content).group(1)
            
            lev_match = re.search(r'LEVERAGE\s*=\s*([0-9]+)', content)
            self.current_lev = lev_match.group(1) if lev_match else "20"
            
            cap_match = re.search(r'MAX_CAPITAL_USDT\s*=\s*([0-9.]+)', content)
            self.current_cap = cap_match.group(1) if cap_match else "500.0"
            
            self.current_sl = re.search(r'STOP_LOSS_PCT\s*=\s*([0-9.]+)', content).group(1)
            self.current_tp = re.search(r'TAKE_PROFIT_PCT\s*=\s*([0-9.]+)', content).group(1)
            
            self.current_use_atr = "USE_ATR = True" in content
            self.current_use_trail = "USE_TRAILING = True" in content
            self.current_use_comp = "USE_COMPOUNDING = True" in content
            
            comp_match = re.search(r'COMPOUND_PCT\s*=\s*([0-9.]+)', content)
            self.current_comp_pct = comp_match.group(1) if comp_match else "2.0"
            
        except Exception as e:
            self.current_mode = "SCALPING"
            self.current_risk = "BALANCED"
            self.current_trade_size = "100.0"
            self.current_lev = "20"
            self.current_cap = "500.0"
            self.current_sl = "0.005"
            self.current_tp = "0.01"
            self.current_use_atr = True
            self.current_use_trail = True
            self.current_use_comp = False
            self.current_comp_pct = "2.0"

    def apply_auto_settings(self):
        # Очищаем
        self.entry_sl.delete(0, 'end')
        self.entry_tp.delete(0, 'end')
        
        mode = self.seg_mode.get()
        risk = self.seg_risk.get()
        
        if mode == "SCALPING":
            if risk == "ЭКОНОМ":
                self.entry_sl.insert(0, "0.3")
                self.entry_tp.insert(0, "0.6")
            elif risk == "БАЛАНС":
                self.entry_sl.insert(0, "0.5")
                self.entry_tp.insert(0, "1.0")
            elif risk == "АГРЕССИВ":
                self.entry_sl.insert(0, "1.0")
                self.entry_tp.insert(0, "2.0")
        else: # NORMAL
            if risk == "ЭКОНОМ":
                self.entry_sl.insert(0, "1.0")
                self.entry_tp.insert(0, "2.0")
            elif risk == "БАЛАНС":
                self.entry_sl.insert(0, "2.0")
                self.entry_tp.insert(0, "4.0")
            elif risk == "АГРЕССИВ":
                self.entry_sl.insert(0, "3.0")
                self.entry_tp.insert(0, "6.0")

    def change_mode(self, value):
        self.current_mode = value
        self.apply_auto_settings()
        self.log_message(f"[ВНИМАНИЕ] Выбран тип торговли: {value}. Не забудь сохранить и переобучить ИИ!")

    def change_risk(self, value):
        risk_map = {"ЭКОНОМ": "CONSERVATIVE", "БАЛАНС": "BALANCED", "АГРЕССИВ": "AGGRESSIVE"}
        self.current_risk = risk_map[value]
        self.apply_auto_settings()
        if value == "АГРЕССИВ":
            self.log_message("[ВНИМАНИЕ] АГРЕССИВНЫЙ РИСК: ИИ не отключается полностью (чтобы не слить депозит), но его требования к сделке снижаются до 50%. Сделок будет больше!")
        elif value == "ЭКОНОМ":
            self.log_message("[ВНИМАНИЕ] РЕЖИМ ЭКОНОМ: Строгий отбор. ИИ зайдет в сделку только при уверенности > 65%.")
        else:
            self.log_message(f"[ВНИМАНИЕ] Риск-менеджмент: {value}. Оптимальные параметры ИИ.")

    def save_config(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                content = f.read()
                
            new_size = float(self.entry_trade_size.get())
            new_lev = int(self.entry_lev.get())
            new_cap = float(self.entry_cap.get())
            new_sl = float(self.entry_sl.get()) / 100
            new_tp = float(self.entry_tp.get()) / 100
            
            new_atr = "True" if self.chk_atr.get() else "False"
            new_trail = "True" if self.chk_trail.get() else "False"
            new_comp = "True" if self.chk_comp.get() else "False"
            new_comp_pct = float(self.entry_comp_pct.get())
            
            content = re.sub(r'TRADING_MODE\s*=\s*"[^"]+"', f'TRADING_MODE = "{self.current_mode}"', content)
            content = re.sub(r'RISK_MODE\s*=\s*"[^"]+"', f'RISK_MODE = "{self.current_risk}"', content)
            
            # Меняем порог уверенности ИИ в зависимости от риска
            if self.current_risk == "CONSERVATIVE":
                content = re.sub(r'ML_PROBABILITY_THRESHOLD\s*=\s*[0-9.]+', 'ML_PROBABILITY_THRESHOLD = 0.65', content)
            elif self.current_risk == "BALANCED":
                content = re.sub(r'ML_PROBABILITY_THRESHOLD\s*=\s*[0-9.]+', 'ML_PROBABILITY_THRESHOLD = 0.55', content)
            elif self.current_risk == "AGGRESSIVE":
                content = re.sub(r'ML_PROBABILITY_THRESHOLD\s*=\s*[0-9.]+', 'ML_PROBABILITY_THRESHOLD = 0.50', content)
            
            # Timeframe and other mode settings are handled dynamically inside config.py based on TRADING_MODE
            content = re.sub(r'TRADE_SIZE_USDT\s*=\s*[0-9.]+', f'TRADE_SIZE_USDT = {new_size}', content)
            content = re.sub(r'LEVERAGE\s*=\s*[0-9]+', f'LEVERAGE = {new_lev}', content)
            content = re.sub(r'MAX_CAPITAL_USDT\s*=\s*[0-9.]+', f'MAX_CAPITAL_USDT = {new_cap}', content)
            content = re.sub(r'STOP_LOSS_PCT\s*=\s*[0-9.]+', f'STOP_LOSS_PCT = {new_sl}', content)
            content = re.sub(r'TAKE_PROFIT_PCT\s*=\s*[0-9.]+', f'TAKE_PROFIT_PCT = {new_tp}', content)
            
            content = re.sub(r'USE_ATR\s*=\s*(True|False)', f'USE_ATR = {new_atr}', content)
            content = re.sub(r'USE_TRAILING\s*=\s*(True|False)', f'USE_TRAILING = {new_trail}', content)
            content = re.sub(r'USE_COMPOUNDING\s*=\s*(True|False)', f'USE_COMPOUNDING = {new_comp}', content)
            content = re.sub(r'COMPOUND_PCT\s*=\s*[0-9.]+', f'COMPOUND_PCT = {new_comp_pct}', content)
            
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(content)
                
            self.log_message(f"[СИСТЕМА] Настройки ({self.current_mode} | {self.current_risk}) успешно сохранены.")
            self.btn_save.configure(text="✅ Сохранено", fg_color="green")
            self.after(2000, lambda: self.btn_save.configure(text="💾 Сохранить", fg_color="gray"))
        except Exception as e:
            self.log_message(f"[ОШИБКА] Не удалось сохранить: {e}")

    def train_ai(self):
        if self.bot_process is not None:
            self.log_message("[ОШИБКА] Сначала останови торговлю перед переобучением!")
            return
            
        self.save_config()
        self.btn_train.configure(state="disabled", text="⏳ Идет обучение...")
        self.log_message("\n" + "="*50)
        self.log_message(f"[СИСТЕМА] Запуск обучения ИИ для режима {self.current_mode}...")
        self.log_message("="*50)
        
        def run_train():
            import sys
            base_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(base_dir, "train_model.py")
            process = subprocess.Popen(
                [sys.executable, "-u", script_path],
                cwd=base_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in process.stdout:
                self.after(0, self.log_message, line.strip())
            process.wait()
            if process.returncode == 0:
                self.after(0, lambda: self.log_message("="*50))
                self.after(0, lambda: self.log_message("[СИСТЕМА] Обучение успешно завершено! Модель сохранена."))
                self.after(0, lambda: self.log_message("="*50))
            else:
                self.after(0, lambda: self.log_message(f"[ОШИБКА] Обучение завершилось с кодом {process.returncode}"))
            self.after(0, lambda: self.btn_train.configure(state="normal", text="🧠 Переобучить ИИ"))
            
        threading.Thread(target=run_train, daemon=True).start()

    def _copy_console_selection(self):
        try:
            selected = self.console.get("sel.first", "sel.last")
            if selected:
                self.clipboard_clear()
                self.clipboard_append(selected)
                return
        except Exception:
            pass
        self._copy_all_console()

    def _select_all_console(self):
        try:
            self.console.tag_add("sel", "1.0", "end")
        except Exception:
            pass

    def _clear_console(self):
        try:
            self.console.delete("1.0", "end")
        except Exception:
            pass

    def _copy_all_console(self):
        try:
            text = self.console.get("1.0", "end-1c")
            if text:
                self.clipboard_clear()
                self.clipboard_append(text)
                self.btn_copy_logs.configure(text="✅ Скопировано!", fg_color="green")
                self.after(1500, lambda: self.btn_copy_logs.configure(text="📋 Скопировать всё", fg_color=["#3B8ED0", "#1F6AA5"]))
        except Exception:
            pass

    def _copy_all_history(self):
        try:
            text = self.history_txt.get("1.0", "end-1c")
            if text:
                self.clipboard_clear()
                self.clipboard_append(text)
                self.btn_copy_hist.configure(text="✅ Скопировано!", fg_color="green")
                self.after(1500, lambda: self.btn_copy_hist.configure(text="📋 Скопировать историю", fg_color=["#3B8ED0", "#1F6AA5"]))
        except Exception:
            pass

    def log_message(self, message):
        self.console.insert("end", message + "\n")
        self.console.see("end")
        
    def update_analytics(self):
        import json
        if os.path.exists("analytics_data.json"):
            try:
                with open("analytics_data.json", "r", encoding="utf-8") as f:
                    trades = json.load(f)
                
                total = len(trades)
                wins = sum(1 for t in trades if t.get('is_win', False))
                pnl = sum(t.get('profit_usdt', t.get('pnl', 0)) for t in trades)
                win_rate = (wins / total * 100) if total > 0 else 0
                
                self.lbl_stat_trades.configure(text=f"Всего закрытых сделок: {total} (➕ {wins} | ➖ {total-wins})")
                
                wr_color = "green" if win_rate >= 50 else "red"
                self.lbl_stat_winrate.configure(text=f"Win-Rate: {win_rate:.1f}%", text_color=wr_color)
                
                pnl_color = "green" if pnl >= 0 else "red"
                sign = "+" if pnl >= 0 else ""
                self.lbl_stat_pnl.configure(text=f"Общий PnL: {sign}${pnl:.2f}", text_color=pnl_color)
            except Exception as e:
                self.log_message(f"Ошибка чтения аналитики: {e}")

    def update_history_loop(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    hist = f.read()
                current_text = self.history_txt.get("1.0", "end-1c")
                if current_text != hist:
                    self.history_txt.delete("1.0", "end")
                    self.history_txt.insert("end", hist)
                    self.history_txt.see("end")
            except Exception:
                pass
        self.after(5000, self.update_history_loop)

    def start_bot(self):
        if os.path.exists("stop.flag"):
            os.remove("stop.flag")
            
        if self.bot_process is None:
            self.log_message("[СИСТЕМА] Запуск торгового ядра (Фьючерсы)...")
            self.lbl_status.configure(text="СТАТУС: АКТИВЕН", text_color="green")
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.btn_graceful.configure(state="normal")
            
            import sys
            base_dir = os.path.dirname(os.path.abspath(__file__))
            main_script = os.path.join(base_dir, "main.py")
            self.bot_process = subprocess.Popen(
                [sys.executable, "-u", main_script],
                cwd=base_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            threading.Thread(target=self.read_output, daemon=True).start()

    def read_output(self):
        while self.bot_process is not None:
            line = self.bot_process.stdout.readline()
            if not line:
                break
            self.after(0, self.log_message, line.strip())
            
        self.after(0, self.handle_bot_stop)

    def graceful_stop(self):
        self.log_message("[СИСТЕМА] Запущен режим плавного завершения. Бот не будет открывать новые сделки и закроется после отработки текущих.")
        with open("stop.flag", "w") as f:
            f.write("stop")
        self.lbl_status.configure(text="СТАТУС: ЗАВЕРШЕНИЕ...", text_color="orange")
        self.btn_graceful.configure(state="disabled")

    def stop_bot(self):
        if self.bot_process is not None:
            self.log_message("[СИСТЕМА] Экстренная остановка бота...")
            self.bot_process.kill()
            self.bot_process = None
            self.handle_bot_stop()

    def handle_bot_stop(self):
        self.lbl_status.configure(text="СТАТУС: ОСТАНОВЛЕН", text_color="red")
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.btn_graceful.configure(state="disabled")
        self.bot_process = None

if __name__ == "__main__":
    app = AlgoBotApp()
    app.mainloop()
