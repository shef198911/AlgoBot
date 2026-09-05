import sys

with open('data_fetcher.py', 'r', encoding='utf-8') as f:
    source = f.read()

start_idx = source.find('    def check_global_trend(self, symbol):')

new_check_trend = '''    def check_global_trend(self, symbol):
        """Определяет глобальный тренд на HTF (старшем таймфрейме)"""
        try:
            from config import TRADING_MODE, TREND_TIMEFRAME
            from ta.trend import EMAIndicator, ADXIndicator
            
            tf = TREND_TIMEFRAME
            if TRADING_MODE == "SCALPING":
                fast_window, slow_window = 21, 50
            else:
                fast_window, slow_window = 9, 21
                
            df = self.get_historical_klines(symbol, tf, limit=100)
            if df is None or df.empty:
                return "RANGE"
                
            df['EMA_FAST'] = EMAIndicator(close=df['close'], window=fast_window).ema_indicator()
            df['EMA_SLOW'] = EMAIndicator(close=df['close'], window=slow_window).ema_indicator()
            
            # Use 14 for ADX
            try:
                adx = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14)
                df['ADX'] = adx.adx()
            except:
                df['ADX'] = 0
            
            last_row = df.iloc[-1]
            fast = last_row.get('EMA_FAST', 0)
            slow = last_row.get('EMA_SLOW', 0)
            close = last_row.get('close', 0)
            adx_val = last_row.get('ADX', 0)
            
            if pd.isna(fast) or pd.isna(slow) or slow == 0:
                return "RANGE"
                
            ema_dist = (fast - slow) / slow
            
            if fast > slow and close > fast:
                if adx_val > 25 and ema_dist > 0.002:
                    return "STRONG_BULL"
                else:
                    return "BULL"
            elif fast < slow and close < fast:
                if adx_val > 25 and ema_dist < -0.002:
                    return "STRONG_BEAR"
                else:
                    return "BEAR"
            else:
                return "RANGE"
                
        except Exception as e:
            self.logger.error(f"Ошибка проверки глобального тренда для {symbol}: {e}")
            return "RANGE"
'''
source = source[:start_idx] + new_check_trend

with open('data_fetcher.py', 'w', encoding='utf-8') as f:
    f.write(source)
