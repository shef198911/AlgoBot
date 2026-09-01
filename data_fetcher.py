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
                'fetchCurrencies': False
            }
        })
        
        if self.use_testnet:
            self.logger.info("Включен режим Testnet (Песочница Binance Futures)")
            # Заменяем URL вручную, так как ccxt.set_sandbox_mode() больше не работает для фьючерсов
            for k in self.exchange.urls['api']:
                if type(self.exchange.urls['api'][k]) is str:
                    self.exchange.urls['api'][k] = self.exchange.urls['api'][k].replace('fapi.binance.com', 'testnet.binancefuture.com')
            try:
                self.exchange.load_time_difference()
            except:
                pass
            
        self.load_markets()

    def load_markets(self, max_retries=3):
        """Пробуем загрузить рынки с повторами при ошибках сети"""
        for attempt in range(max_retries):
            try:
                self.exchange.load_markets()
                self.logger.info("Рынки успешно загружены.")
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
            # Получаем свечи
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
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
        """Мульти-таймфрейм анализ: определяет глобальный тренд"""
        try:
            from config import TRADING_MODE
            
            # Для скальпинга (1m) глобальный тренд - это 15m
            # Для нормальной торговли (15m) глобальный тренд - это 4h
            if TRADING_MODE == "SCALPING":
                tf = '15m'
                fast_window, slow_window = 21, 50
            else:
                tf = '1h'
                fast_window, slow_window = 9, 21
                
            df = self.get_historical_klines(symbol, tf, limit=100)
            if df is None or df.empty:
                return 0
                
            from ta.trend import EMAIndicator
            df['EMA_FAST'] = EMAIndicator(close=df['close'], window=fast_window).ema_indicator()
            df['EMA_SLOW'] = EMAIndicator(close=df['close'], window=slow_window).ema_indicator()
            
            last_row = df.iloc[-1]
            if pd.isna(last_row['EMA_FAST']) or pd.isna(last_row['EMA_SLOW']):
                return 0
                
            if last_row['EMA_FAST'] > last_row['EMA_SLOW']:
                return 1 # Разрешен только LONG
            elif last_row['EMA_FAST'] < last_row['EMA_SLOW']:
                return -1 # Разрешен только SHORT
            return 0
        except Exception as e:
            self.logger.error(f"Ошибка проверки глобального тренда для {symbol}: {e}")
            return 0
