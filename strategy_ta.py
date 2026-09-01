import pandas as pd
from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import VolumeWeightedAveragePrice
from config import logger, TRADING_MODE

class TAStrategy:
    def __init__(self):
        self.logger = logger.getChild("TAStrategy")

    def generate_features_and_signals(self, df):
        if df is None or df.empty:
            return None

        data = df.copy()
        
        try:
            # 1. Расчет индикаторов
            if TRADING_MODE == "SCALPING":
                fast_window, slow_window, rsi_window = 9, 21, 14
            else:
                fast_window, slow_window, rsi_window = 21, 50, 14

            # Трендовые (EMA)
            data['EMA_FAST'] = EMAIndicator(close=data['close'], window=fast_window).ema_indicator()
            data['EMA_SLOW'] = EMAIndicator(close=data['close'], window=slow_window).ema_indicator()
            
            # Моментум (RSI)
            data['RSI'] = RSIIndicator(close=data['close'], window=rsi_window).rsi()
            
            # Волатильность (ATR + Bollinger Bands)
            data['ATRr'] = AverageTrueRange(high=data['high'], low=data['low'], close=data['close'], window=14).average_true_range()
            bb = BollingerBands(close=data['close'], window=20, window_dev=2)
            data['BB_UPPER'] = bb.bollinger_hband()
            data['BB_LOWER'] = bb.bollinger_lband()
            
            # Сила тренда (ADX)
            adx = ADXIndicator(high=data['high'], low=data['low'], close=data['close'], window=14)
            data['ADX'] = adx.adx()
            
            # Объем (VWAP)
            vwap = VolumeWeightedAveragePrice(high=data['high'], low=data['low'], close=data['close'], volume=data['volume'], window=14)
            data['VWAP'] = vwap.volume_weighted_average_price()
            
            # --- НОВЫЕ ПРИЗНАКИ ДЛЯ ИИ ПРО-УРОВНЯ ---
            # 1. Ширина полос Боллинджера (измеряет "сжатие" волатильности перед прострелом)
            data['BB_WIDTH'] = (data['BB_UPPER'] - data['BB_LOWER']) / bb.bollinger_mavg()
            
            # 2. Скорость изменения цены (Price Rate of Change, Momentum)
            data['PRICE_ROC'] = data['close'].pct_change(periods=14)
            
            # 3. Аномалии объема (Наблюдается ли всплеск объема?)
            data['VOL_RATIO'] = data['volume'] / data['volume'].rolling(window=20).mean()
            
            # 4. Расстояние до VWAP (перепроданность/перекупленность внутри дня)
            data['VWAP_DIST'] = (data['close'] - data['VWAP']) / data['VWAP']

            # Очищаем от NaN (индикаторы с окном 200 дадут 200 пустых строк, поэтому чистим)
            data.dropna(inplace=True)
            
            # 2. Логика генерации контекстно-зависимого сигнала (Синергия / Командная работа)
            def get_signal(row):
                c = row['close']
                
                # РЕЖИМ 1: СИЛЬНЫЙ ТРЕНД (ADX > 25)
                if row['ADX'] > 25:
                    # Восходящий тренд: Быстрая EMA выше медленной, цена выше VWAP (подтверждение объемом)
                    if row['EMA_FAST'] > row['EMA_SLOW'] and c > row['VWAP']:
                        # Ищем откат (pullback), а не покупаем на хаях
                        if row['RSI'] < 60 and c > row['BB_LOWER']:
                            return 1 # BUY
                    
                    # Нисходящий тренд: Быстрая EMA ниже медленной, цена ниже VWAP
                    elif row['EMA_FAST'] < row['EMA_SLOW'] and c < row['VWAP']:
                        # Ищем отскок вверх
                        if row['RSI'] > 40 and c < row['BB_UPPER']:
                            return -1 # SELL
                
                # РЕЖИМ 2: БОКОВИК / ФЛЭТ (ADX <= 25)
                else:
                    # В боковике трендовые индикаторы (EMA) врут. Доверяем границам Боллинджера и RSI.
                    # Покупка от нижней границы
                    if c <= row['BB_LOWER'] and row['RSI'] < 35:
                        return 1 # BUY
                    
                    # Продажа от верхней границы
                    elif c >= row['BB_UPPER'] and row['RSI'] > 65:
                        return -1 # SELL
                        
                return 0 # Ждем
            
            data['ta_signal'] = data.apply(get_signal, axis=1)
            
            return data
            
        except Exception as e:
            self.logger.error(f"Ошибка при расчете индикаторов: {e}")
            return None
