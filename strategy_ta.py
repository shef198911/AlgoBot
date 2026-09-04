import pandas as pd
from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import VolumeWeightedAveragePrice
from config import logger, TRADING_MODE, MIN_SR_DISTANCE_PCT, MIN_SETUP_SCORE
from market_structure import MarketStructureEngine, enrich_with_market_structure


from entry_gate import EntryGate, entry_stats
class TAStrategy:
    def __init__(self):
        self.logger = logger.getChild("TAStrategy")

    def generate_features_and_signals(self, df, htf_trend=None):
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

            # 2. Обогащение полноценным движком рыночной структуры (S/R Zones, State Machine, Breakout-Retest)
            engine = MarketStructureEngine()
            data = engine.analyze(data)
            
            min_sr = MIN_SR_DISTANCE_PCT if 'MIN_SR_DISTANCE_PCT' in globals() else 0.005

            # 3. Индикаторное подтверждение сетапов от MarketStructureEngine

            results = []
            symbol_str = getattr(self, "current_symbol", "UNKNOWN")
            total_rows = len(data)
            for i, (_, row) in enumerate(data.iterrows()):
                effective_trend = htf_trend if htf_trend is not None else row.get("HTF_TREND", row.get("GLOBAL_TREND", "RANGE"))
                is_last = (i == total_rows - 1)
                is_valid, reject_reason = EntryGate.validate(row, effective_trend, symbol_str, do_log=is_last)
                if is_valid:
                    results.append((row.get('engine_signal', 0), row.get('engine_setup', 'None')))
                else:
                    results.append((0, "None"))
                    
            data['ta_signal'] = [r[0] for r in results]
            data['ta_setup'] = [r[1] for r in results]
            data['setup_score'] = data['SETUP_SCORE']
            
            return data
            
        except Exception as e:
            self.logger.error(f"Ошибка при расчете индикаторов и структуры: {e}")
            return None
