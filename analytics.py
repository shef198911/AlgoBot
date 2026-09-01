import json
import os
from config import logger

ANALYTICS_FILE = "analytics_data.json"

class AnalyticsManager:
    def __init__(self):
        self.logger = logger.getChild("Analytics")
        self.trades = []
        self.load_data()

    def load_data(self):
        if os.path.exists(ANALYTICS_FILE):
            try:
                with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
                    self.trades = json.load(f)
            except Exception as e:
                self.logger.error(f"Ошибка загрузки аналитики: {e}")
                self.trades = []
        else:
            self.trades = []

    def save_data(self):
        try:
            with open(ANALYTICS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.trades, f, indent=4)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения аналитики: {e}")

    def record_trade(self, symbol, side, entry_price, exit_price, pnl_usdt, ai_confidence=0.0):
        import time
        trade = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "profit_usdt": pnl_usdt,
            "is_win": pnl_usdt > 0,
            "ai_confidence": ai_confidence
        }
        self.trades.append(trade)
        self.save_data()
        self.logger.info(f"Сделка по {symbol} записана в аналитику (PnL: {pnl_usdt:.2f} USDT)")

    def get_stats(self):
        total_trades = len(self.trades)
        if total_trades == 0:
            return {"win_rate": 0, "total_pnl": 0, "total_trades": 0, "wins": 0, "losses": 0}

        wins = sum(1 for t in self.trades if t.get('is_win', False))
        losses = total_trades - wins
        win_rate = (wins / total_trades) * 100
        total_pnl = sum(t.get('profit_usdt', t.get('pnl', 0)) for t in self.trades)

        return {
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses
        }

analytics_manager = AnalyticsManager()
