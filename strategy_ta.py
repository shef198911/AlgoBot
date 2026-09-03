import pandas as pd
from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import VolumeWeightedAveragePrice
from config import logger, TRADING_MODE, MIN_SR_DISTANCE_PCT
from market_structure import enrich_with_market_structure

class TAStrategy:
    def __init__(self):
        self.logger = logger.getChild("TAStrategy")

    def generate_features_and_signals(self, df):
        if df is None or df.empty:
            return None

        data = df.copy()
        
        try:
            # 1. Расчет базовых индикаторов
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
            
            # Объем (VWAP) и аномалии объема (защита от нулевого объема)
            if data['volume'].sum() > 0:
                vwap = VolumeWeightedAveragePrice(high=data['high'], low=data['low'], close=data['close'], volume=data['volume'], window=14)
                data['VWAP'] = vwap.volume_weighted_average_price().fillna(data['close'])
                data['VOL_RATIO'] = (data['volume'] / data['volume'].rolling(window=20).mean()).fillna(1.0)
            else:
                data['VWAP'] = data['close']
                data['VOL_RATIO'] = 1.0
            
            # Дополнительные производные признаки
            data['BB_WIDTH'] = (data['BB_UPPER'] - data['BB_LOWER']) / bb.bollinger_mavg()
            data['PRICE_ROC'] = data['close'].pct_change(periods=14)
            data['VWAP_DIST'] = ((data['close'] - data['VWAP']) / data['VWAP']).fillna(0.0)

            # Очищаем от начальных NaN после rolling индикаторов
            data.dropna(inplace=True)
            if data.empty:
                return None

            # 2. Обогащение рыночной структурой и Price Action (S/R, Свинги, Отторжения, Ретесты)
            data = enrich_with_market_structure(data)
            
            min_sr = MIN_SR_DISTANCE_PCT if 'MIN_SR_DISTANCE_PCT' in globals() else 0.005

            # 3. Логика генерации Price Action сетапов с подтверждением индикаторами
            def get_signal_and_setup(row):
                c = row['close']
                
                # --- ВЕТКА LONG (BUY = 1) ---
                # Фильтр "Стена": Не покупаем, если прямо над головой стоит близкое сопротивление
                if row['DIST_RES_PCT'] >= min_sr:
                    # Сетап 1: Breakout & Retest (Пробой уровня с подтвержденным ретестом)
                    if row['IS_RETEST_LONG'] == 1 and (row['BULLISH_REJECTION'] == 1 or c > row['open']) and row['RSI'] < 65:
                        return 1, "Breakout & Retest"
                    
                    # Сетап 2: Support Bounce (Отскок от поддержки с пин-баром откупа)
                    if row['DIST_SUP_PCT'] <= 0.008 and row['BULLISH_REJECTION'] == 1 and row['RSI'] < 55:
                        return 1, "Support Bounce"
                        
                    # Сетап 3: Trend Pullback (Откат по бычьему тренду с подтверждением объема)
                    if row['ADX'] > 25 and row['EMA_FAST'] > row['EMA_SLOW'] and c > row['VWAP'] and row['RSI'] < 60 and c > row['BB_LOWER'] and row['MARKET_STRUCTURE'] >= 0:
                        return 1, "Trend Pullback"
                        
                    # Сетап 4: Range Bounce (Отбой от нижней границы боковика)
                    if row['ADX'] <= 25 and (c <= row['BB_LOWER'] or row['DIST_SUP_PCT'] <= 0.005) and row['RSI'] < 35 and row['BULLISH_REJECTION'] == 1:
                        return 1, "Range Bounce"

                # --- ВЕТКА SHORT (SELL = -1) ---
                # Фильтр "Стена": Не продаем, если прямо под ногами стоит близкая поддержка
                if row['DIST_SUP_PCT'] >= min_sr:
                    # Сетап 1: Breakdown & Retest (Пробой поддержки с ретестом снизу)
                    if row['IS_RETEST_SHORT'] == 1 and (row['BEARISH_REJECTION'] == 1 or c < row['open']) and row['RSI'] > 35:
                        return -1, "Breakdown & Retest"
                    
                    # Сетап 2: Resistance Rejection (Отбой от сопротивления с пин-баром продаж)
                    if row['DIST_RES_PCT'] <= 0.008 and row['BEARISH_REJECTION'] == 1 and row['RSI'] > 45:
                        return -1, "Resistance Rejection"
                        
                    # Сетап 3: Trend Pullback Down (Откат по медвежьему тренду)
                    if row['ADX'] > 25 and row['EMA_FAST'] < row['EMA_SLOW'] and c < row['VWAP'] and row['RSI'] > 40 and c < row['BB_UPPER'] and row['MARKET_STRUCTURE'] <= 0:
                        return -1, "Trend Pullback Down"
                        
                    # Сетап 4: Range Rejection (Отбой от верхней границы боковика)
                    if row['ADX'] <= 25 and (c >= row['BB_UPPER'] or row['DIST_RES_PCT'] <= 0.005) and row['RSI'] > 65 and row['BEARISH_REJECTION'] == 1:
                        return -1, "Range Rejection"

                return 0, "None"

            results = [get_signal_and_setup(row) for _, row in data.iterrows()]
            data['ta_signal'] = [r[0] for r in results]
            data['ta_setup'] = [r[1] for r in results]
            
            return data
            
        except Exception as e:
            self.logger.error(f"Ошибка при расчете индикаторов и структуры: {e}")
            return None
