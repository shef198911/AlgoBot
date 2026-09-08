import sys

def patch_executor_history():
    with open('G:/AlgoBot/executor.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Patch `_log_risk_reject` to write to `trade_history.txt`
    reject_hook = '''        self.logger.warning(log_msg)
        try:
            import time
            with open("trade_history.txt", "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {symbol} | REJECT | Ошибка: {reject_reason} | Risk USDT: {risk_usdt:.2f}\\n")
        except Exception:
            pass'''
    content = content.replace('        self.logger.warning(log_msg)', reject_hook)

    # 2. Patch exit logic to write to `trade_history.txt`
    exit_hook = '''                try:
                    import time
                    with open("trade_history.txt", "a", encoding="utf-8") as f:
                        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {symbol} | EXIT | Вход: {pos_data.get('entry', 0):.4f} | Выход: {exit_price:.4f} | PnL: {pnl:.2f} USDT\\n")
                except Exception:
                    pass
                try:
                    import datetime'''
    content = content.replace('                try:\n                    import datetime', exit_hook)

    with open('G:/AlgoBot/executor.py', 'w', encoding='utf-8') as f:
        f.write(content)

patch_executor_history()
