import ccxt
import pandas as pd
import time
from config import logger

class DataFetcher:
    def __init__(self, use_testnet=False, api_key="", api_secret=""):
        self.logger = logger.getChild("DataFetcher")
        self.use_testnet = use_testnet
        
        # Настройка клиента ccxt
        self.exchange = ccxt.binanceusdm({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True, # ccxt сам будет стараться не нарушать лимиты
            'options': {
                'defaultType': 'future',
                'adjustForTimeDifference': True,
                'recvWindow': 10000,
                'fetchCurrencies': False
            }
        })
        
        if self.use_testnet:
            if not getattr(DataFetcher, '_testnet_logged', False):
                self.logger.info("Включен режим Testnet (Песочница Binance Futures)")
                DataFetcher._testnet_logged = True
            # Заменяем URL вручную, так как ccxt.set_sandbox_mode() больше не работает для фьючерсов
            for k in self.exchange.urls['api']:
                if type(self.exchange.urls['api'][k]) is str:
                    self.exchange.urls['api'][k] = self.exchange.urls['api'][k].replace('fapi.binance.com', 'testnet.binancefuture.com')
                    
        try:
            self.exchange.load_time_difference()
        except Exception as e:
            self.logger.warning(f"Предупреждение синхронизации времени: {e}")
            
        self.load_markets()

    def load_markets(self, max_retries=3):
        """Пробуем загрузить рынки с повторами при ошибках сети"""
        for attempt in range(max_retries):
            try:
                self.exchange.load_markets()
                if not getattr(DataFetcher, '_markets_logged', False):
                    self.logger.info("Рынки успешно загружены.")
                    DataFetcher._markets_logged = True
                return
            except ccxt.NetworkError as e:
                self.logger.warning(f"Ошибка сети при загрузке рынков (Попытка {attempt+1}/{max_retries}): {e}")
                time.sleep(2 ** attempt) # Экспоненциальная задержка: 1с, 2с, 4с
            except Exception as e:
                self.logger.error(f"Критическая ошибка при инициализации биржи: {e}")
                raise

    def get_historical_klines(self, symbol, timeframe, limit=100):
        """Получает историю свечей и возвращает pandas DataFrame"""
        try:
            if limit <= 1500:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            else:
                timeframe_ms = self.exchange.parse_timeframe(timeframe) * 1000
                now = self.exchange.milliseconds()
                since = int(now - (limit * timeframe_ms))
                all_ohlcv = []
                while since < now:
                    batch = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1500)
                    if not batch:
                        break
                    all_ohlcv.extend(batch)
                    since = batch[-1][0] + timeframe_ms
                ohlcv = all_ohlcv[-limit:]
            
            # Конвертируем в DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Closed-candle enforcement: удаляем последнюю (текущую незакрытую) свечу
            if not df.empty:
                df = df.iloc[:-1].copy()
            
            return df
        except ccxt.RateLimitExceeded:
            self.logger.warning("Превышен лимит запросов к API. Ждем...")
            time.sleep(5)
            return None
        except Exception as e:
            self.logger.error(f"Ошибка при получении свечей {symbol}: {e}")
            return None
            
    def check_global_trend(self, symbol):
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
