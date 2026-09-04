import pandas as pd
from ta.trend import EMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import VolumeWeightedAveragePrice
from config import logger, TRADING_MODE, MIN_SR_DISTANCE_PCT, MIN_SETUP_SCORE
from market_structure import MarketStructureEngine, enrich_with_market_structure


# Global entry statistics
entry_stats = {
    'TA_CANDIDATES': 0,
    'ENTRY_GATE_PASS': 0,
    'REJECT_NO_BROKEN_LEVEL': 0,
    'REJECT_NO_CONFIRMATION': 0,
    'REJECT_BAD_STRUCTURE': 0,
    'REJECT_BAD_GLOBAL_TREND': 0,
    'REJECT_CANDLE_CLOSE': 0,
    'REJECT_NO_REAL_SWEEP': 0,
    'REJECT_NOT_IN_RANGE': 0,
    'REJECT_UNKNOWN_SETUP': 0,
    'REJECT_LOW_SCORE': 0,
    'REJECT_SR_TOO_CLOSE': 0,
    'REJECT_RSI_EXTREME': 0
}
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

            # 2. Обогащение полноценным движком рыночной структуры (S/R Zones, State Machine, Breakout-Retest)
            engine = MarketStructureEngine()
            data = engine.analyze(data)
            
            min_sr = MIN_SR_DISTANCE_PCT if 'MIN_SR_DISTANCE_PCT' in globals() else 0.005

            # 3. Индикаторное подтверждение сетапов от MarketStructureEngine
            def get_global_trend(row):
                fast = row.get('EMA_FAST', 0)
                slow = row.get('EMA_SLOW', 0)
                close = row.get('close', 0)
                adx = row.get('ADX', 0)
                
                if pd.isna(fast) or pd.isna(slow) or slow == 0:
                    return "RANGE"
                    
                ema_dist = (fast - slow) / slow
                
                if fast > slow and close > fast:
                    if adx > 25 and ema_dist > 0.002:
                        return "STRONG_BULL"
                    else:
                        return "BULL"
                elif fast < slow and close < fast:
                    if adx > 25 and ema_dist < -0.002:
                        return "STRONG_BEAR"
                    else:
                        return "BEAR"
                else:
                    return "RANGE"

            data['GLOBAL_TREND'] = data.apply(get_global_trend, axis=1)

            def get_confirmed_signal(row):
                eng_sig = row.get('engine_signal', 0)
                eng_setup = row.get('engine_setup', 'None')
                score = row.get('SETUP_SCORE', 0)
                rsi = row.get('RSI', 50)
                
                if eng_sig == 0 or eng_setup == "None":
                    return 0, "None"
                    
                entry_stats['TA_CANDIDATES'] += 1
                    
                ctx = row.get('engine_context', {})
                if not isinstance(ctx, dict):
                    ctx = {}
                    
                global_trend = row.get('GLOBAL_TREND', 'RANGE')
                
                mandatory_pass = False
                reject_reason = "NO_REASON"
                
                struct_val = row.get('MARKET_STRUCTURE', 0)
                is_bullish_struct = (struct_val == 1.0)
                is_bearish_struct = (struct_val == -1.0)
                
                sr_strength = row.get('SR_STRENGTH', 50.0)
                req_dist = min_sr * max(1.0, (sr_strength / 50.0))
                
                if eng_sig == 1.0: # LONG
                    if eng_setup == "BREAKOUT_RETEST":
                        if ctx.get('broken_level') is None:
                            reject_reason = "NO_BROKEN_LEVEL"
                        elif not ctx.get('rejection_low'):
                            reject_reason = "NO_BULLISH_CONFIRMATION"
                        elif is_bearish_struct:
                            reject_reason = "BEARISH_STRUCTURE"
                        elif global_trend not in ['BULL', 'STRONG_BULL']:
                            reject_reason = "BAD_GLOBAL_TREND"
                        elif row.get('close', 0) <= row.get('open', 0):
                            reject_reason = "RED_CANDLE_CLOSE"
                        else:
                            mandatory_pass = True
                            
                    elif eng_setup == "LIQUIDITY_SWEEP_LONG":
                        if not ctx.get('sweep_low'):
                            reject_reason = "NO_REAL_SWEEP"
                        elif not ctx.get('rejection_low'):
                            reject_reason = "NO_BULLISH_CONFIRMATION"
                        elif is_bearish_struct:
                            reject_reason = "BEARISH_STRUCTURE"
                        elif global_trend not in ['BULL', 'STRONG_BULL']:
                            reject_reason = "BAD_GLOBAL_TREND"
                        else:
                            mandatory_pass = True
                            
                    elif eng_setup == "TREND_PULLBACK":
                        if not is_bullish_struct:
                            reject_reason = "NO_BULLISH_STRUCTURE"
                        elif not ctx.get('rejection_low'):
                            reject_reason = "NO_BULLISH_CONFIRMATION"
                        elif global_trend not in ['BULL', 'STRONG_BULL']:
                            reject_reason = "BAD_GLOBAL_TREND"
                        else:
                            mandatory_pass = True
                            
                    elif eng_setup in ["RANGE_BOUNCE", "SUPPORT_BOUNCE"]:
                        if not ctx.get('rejection_low'):
                            reject_reason = "NO_BULLISH_CONFIRMATION"
                        elif is_bullish_struct or is_bearish_struct:
                            reject_reason = "NOT_IN_RANGE_STRUCTURE"
                        else:
                            mandatory_pass = True
                    else:
                        reject_reason = "UNKNOWN_SETUP"

                    if mandatory_pass:
                        if score < MIN_SETUP_SCORE:
                            mandatory_pass = False
                            reject_reason = "LOW_SCORE"
                        elif row.get('DIST_RES_PCT', 1.0) < req_dist:
                            mandatory_pass = False
                            reject_reason = "RESISTANCE_TOO_CLOSE"
                        elif rsi > 75:
                            mandatory_pass = False
                            reject_reason = "RSI_OVERBOUGHT"

                elif eng_sig == -1.0: # SHORT
                    if eng_setup == "BREAKDOWN_RETEST":
                        if ctx.get('broken_level') is None:
                            reject_reason = "NO_BROKEN_LEVEL"
                        elif not ctx.get('rejection_high'):
                            reject_reason = "NO_BEARISH_CONFIRMATION"
                        elif is_bullish_struct:
                            reject_reason = "BULLISH_STRUCTURE"
                        elif global_trend not in ['BEAR', 'STRONG_BEAR']:
                            reject_reason = "BAD_GLOBAL_TREND"
                        elif row.get('close', 0) >= row.get('open', 0):
                            reject_reason = "GREEN_CANDLE_CLOSE"
                        else:
                            mandatory_pass = True
                            
                    elif eng_setup == "LIQUIDITY_SWEEP_SHORT":
                        if not ctx.get('sweep_high'):
                            reject_reason = "NO_REAL_SWEEP"
                        elif not ctx.get('rejection_high'):
                            reject_reason = "NO_BEARISH_CONFIRMATION"
                        elif is_bullish_struct:
                            reject_reason = "BULLISH_STRUCTURE"
                        elif global_trend not in ['BEAR', 'STRONG_BEAR']:
                            reject_reason = "BAD_GLOBAL_TREND"
                        else:
                            mandatory_pass = True
                            
                    elif eng_setup == "TREND_PULLBACK_DOWN":
                        if not is_bearish_struct:
                            reject_reason = "NO_BEARISH_STRUCTURE"
                        elif not ctx.get('rejection_high'):
                            reject_reason = "NO_BEARISH_CONFIRMATION"
                        elif global_trend not in ['BEAR', 'STRONG_BEAR']:
                            reject_reason = "BAD_GLOBAL_TREND"
                        else:
                            mandatory_pass = True
                            
                    elif eng_setup in ["RANGE_REJECTION", "RESISTANCE_REJECTION"]:
                        if not ctx.get('rejection_high'):
                            reject_reason = "NO_BEARISH_CONFIRMATION"
                        elif is_bullish_struct or is_bearish_struct:
                            reject_reason = "NOT_IN_RANGE_STRUCTURE"
                        else:
                            mandatory_pass = True
                    else:
                        reject_reason = "UNKNOWN_SETUP"

                    if mandatory_pass:
                        if score < MIN_SETUP_SCORE:
                            mandatory_pass = False
                            reject_reason = "LOW_SCORE"
                        elif row.get('DIST_SUP_PCT', 1.0) < req_dist:
                            mandatory_pass = False
                            reject_reason = "SUPPORT_TOO_CLOSE"
                        elif rsi < 25:
                            mandatory_pass = False
                            reject_reason = "RSI_OVERSOLD"

                if not mandatory_pass:
                    # Map to stats keys
                    if "BROKEN_LEVEL" in reject_reason: entry_stats['REJECT_NO_BROKEN_LEVEL'] += 1
                    elif "CONFIRMATION" in reject_reason: entry_stats['REJECT_NO_CONFIRMATION'] += 1
                    elif "STRUCTURE" in reject_reason: entry_stats['REJECT_BAD_STRUCTURE'] += 1
                    elif "GLOBAL_TREND" in reject_reason: entry_stats['REJECT_BAD_GLOBAL_TREND'] += 1
                    elif "CANDLE" in reject_reason: entry_stats['REJECT_CANDLE_CLOSE'] += 1
                    elif "SWEEP" in reject_reason: entry_stats['REJECT_NO_REAL_SWEEP'] += 1
                    elif "SCORE" in reject_reason: entry_stats['REJECT_LOW_SCORE'] += 1
                    elif "CLOSE" in reject_reason: entry_stats['REJECT_SR_TOO_CLOSE'] += 1
                    elif "RSI" in reject_reason: entry_stats['REJECT_RSI_EXTREME'] += 1
                    else: entry_stats['REJECT_UNKNOWN_SETUP'] += 1
                    
                    symbol_str = getattr(self, "current_symbol", "UNKNOWN")
                    direction_str = "LONG" if eng_sig == 1.0 else "SHORT"
                    
                    self.logger.info(
                        f"\n[ENTRY CHECK REJECT]\n"
                        f"SYMBOL={symbol_str} {direction_str}\n"
                        f"SETUP={eng_setup}\n"
                        f"SCORE={score}\n"
                        f"STRUCTURE_BULL={is_bullish_struct} BEAR={is_bearish_struct}\n"
                        f"GLOBAL_TREND={global_trend}\n"
                        f"ENTRY_GATE=FAIL\n"
                        f"REASON={reject_reason}\n"
                    )
                    return 0, "None"
                    
                entry_stats['ENTRY_GATE_PASS'] += 1
                symbol_str = getattr(self, "current_symbol", "UNKNOWN")
                direction_str = "LONG" if eng_sig == 1.0 else "SHORT"
                self.logger.info(
                    f"\n[ENTRY CHECK PASS]\n"
                    f"SYMBOL={symbol_str} {direction_str}\n"
                    f"SETUP={eng_setup}\n"
                    f"SCORE={score}\n"
                    f"STRUCTURE_BULL={is_bullish_struct} BEAR={is_bearish_struct}\n"
                    f"GLOBAL_TREND={global_trend}\n"
                    f"ENTRY_GATE=PASS\n"
                )
                return eng_sig, eng_setup

            results = [get_confirmed_signal(row) for _, row in data.iterrows()]
            data['ta_signal'] = [r[0] for r in results]
            data['ta_setup'] = [r[1] for r in results]
            data['setup_score'] = data['SETUP_SCORE']
            
            return data
            
        except Exception as e:
            self.logger.error(f"Ошибка при расчете индикаторов и структуры: {e}")
            return None
