import re

with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
    content = f.read()

injection = """                        self.logger.info(f"Position closed. PnL {pnl:.2f}, fees {fees:.2f}")

                        try:
                            import time
                            from telegram_notifier import TelegramNotifier
                            tg = TelegramNotifier()
                            entry_p = float(pos_data.get('entry', 0.0))
                            side_p = str(pos_data.get('side', 'UNKNOWN')).upper()
                            win_loss = "WIN 💰" if pnl > 0 else "LOSS 📉"
                            req_margin = float(pos_data.get('margin_required', abs(pnl) + 0.1))
                            pnl_pct = (pnl / req_margin) * 100 if req_margin > 0 else 0.0
                            
                            msg = f"🏁 <b>Сделка ЗАКРЫТА: {symbol} ({side_p})</b>\\nРезультат: {win_loss}\\nPnL: {pnl:.2f} USDT ({pnl_pct:.2f}%)\\nВход: {entry_p:.5f}\\nВыход: {exit_price:.5f}"
                            tg.send_message(msg)
                            
                            with open("trade_history.txt", "a", encoding="utf-8") as hist_f:
                                hist_f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {symbol} | {side_p} CLOSED | PnL: {pnl:.2f} USDT | Вход: {entry_p:.5f} | Выход: {exit_price:.5f}\\n")
                        except Exception as e:
                            self.logger.error(f"Failed to send close notification for {symbol}: {e}")
"""

content = content.replace('                        self.logger.info(f"Position closed. PnL {pnl:.2f}, fees {fees:.2f}")\n', injection)

with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Injected close notifications!")
