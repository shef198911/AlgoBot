import re

with open('desktop_app.py', 'r', encoding='utf-8') as f:
    code = f.read()

btn_panic_code = '''        self.btn_stop = ctk.CTkButton(self.controls, text="Экстренный стоп", command=self.stop_bot, fg_color="red", hover_color="darkred", state="disabled")
        self.btn_stop.pack(side="left", expand=True, padx=5)
        
        self.btn_panic = ctk.CTkButton(self.controls, text="🚨 ПАНИКА (ЗАКРЫТЬ ВСЕ)", command=self.panic_close_all, fg_color="#8B0000", hover_color="#660000")
        self.btn_panic.pack(side="left", expand=True, padx=5)'''

code = code.replace('''        self.btn_stop = ctk.CTkButton(self.controls, text="Экстренный стоп", command=self.stop_bot, fg_color="red", hover_color="darkred", state="disabled")
        self.btn_stop.pack(side="left", expand=True, padx=5)''', btn_panic_code)

panic_method = '''    def stop_bot(self):
        if self.bot_process is not None:
            self.log_message("[!] Остановка торгового бота (экстренный стоп)...")
            open("stop.flag", "w").close()
            try:
                self.bot_process.kill()
            except:
                pass
            self.bot_process = None
            
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.lbl_status.configure(text="Статус: Остановлен", text_color="red")
            self.log_message("[INFO] Бот успешно остановлен. ПОЗИЦИИ И ОРДЕРА НЕ БЫЛИ ЗАКРЫТЫ.")
            
    def panic_close_all(self):
        import threading
        def _do_panic():
            self.log_message("🚨 [ПАНИКА] АКТИВИРОВАН ЭКСТРЕННЫЙ РЕЖИМ!")
            self.stop_bot() # Сначала глушим самого бота
            try:
                from data_fetcher import DataFetcher
                from config import API_KEY, API_SECRET, USE_TESTNET
                fetcher = DataFetcher(use_testnet=USE_TESTNET, api_key=API_KEY, api_secret=API_SECRET)
                positions = fetcher.exchange.fetch_positions()
                
                # Закрываем все позиции
                for pos in positions:
                    contracts = float(pos.get('contracts', 0))
                    if contracts > 0:
                        symbol = pos['symbol']
                        side = pos['side'].upper()
                        close_side = "sell" if side == "LONG" else "buy"
                        self.log_message(f"🚨 [ПАНИКА] Закрытие позиции {symbol} {side} по рынку...")
                        try:
                            fetcher.exchange.cancel_all_orders(symbol)
                            fetcher.exchange.create_market_order(symbol, close_side, contracts, params={'reduceOnly': True})
                        except Exception as e:
                            self.log_message(f"❌ Ошибка при закрытии {symbol}: {e}")
                self.log_message("✅ [ПАНИКА] Все позиции и ордера закрыты.")
                self.refresh_positions()
            except Exception as e:
                self.log_message(f"❌ Ошибка паники: {e}")
                
        threading.Thread(target=_do_panic, daemon=True).start()'''

code = code.replace('''    def stop_bot(self):
        if self.bot_process is not None:
            self.log_message("[!] Остановка торгового бота...")
            open("stop.flag", "w").close()
            try:
                self.bot_process.kill()
            except:
                pass
            self.bot_process = None
            
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.lbl_status.configure(text="Статус: Остановлен", text_color="red")''', panic_method)

with open('desktop_app.py', 'w', encoding='utf-8') as f:
    f.write(code)
