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
