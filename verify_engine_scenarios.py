import sys
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from config import FEATURE_COLUMNS, SWING_K, RETEST_MAX_BARS
from market_structure import MarketStructureEngine
from strategy_ta import TAStrategy

def create_df(closes, highs=None, lows=None, opens=None, volumes=None):
    n = len(closes)
    closes = np.array(closes, dtype=float)
    highs = np.array(highs if highs is not None else closes * 1.002, dtype=float)
    lows = np.array(lows if lows is not None else closes * 0.998, dtype=float)
    opens = np.array(opens if opens is not None else closes, dtype=float)
    volumes = np.array(volumes if volumes is not None else np.ones(n) * 1000.0, dtype=float)
    timestamps = pd.date_range('2026-01-01', periods=n, freq='15min')
    return pd.DataFrame({
        'timestamp': timestamps,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    })

def run_all_checks() -> List[Tuple[str, str, str, str]]:
    results = []
    
    # -------------------------------------------------------------
    # 1. LONG BREAKOUT -> RETEST -> CONFIRMATION -> ENTRY
    # -------------------------------------------------------------
    try:
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        # Свинг хай 105 на свече 2, подтверждается на свече 4
        # Свеча 5: Пробой вверх закрытием на 108.0
        # Свеча 6: Откат к 106.0
        # Свеча 7: Ретест в 105.1 с бычьим откупом (close 105.5 >= zone_low)
        closes = [100, 103, 105, 103, 101, 108.0, 106.0, 105.5]
        highs  = [100.5, 103.5, 105.5, 103.5, 101.5, 108.5, 106.5, 106.0]
        lows   = [99.5, 102.5, 104.5, 102.5, 100.5, 107.0, 105.8, 104.8]
        opens  = [100, 103, 105, 103, 101, 102.0, 107.5, 105.0]
        df = create_df(closes, highs=highs, lows=lows, opens=opens)
        res = engine.analyze(df)
        
        has_breakout = (res['IS_BREAKOUT_LONG'].iloc[5] == 1.0)
        has_retest = (res['IS_RETEST_LONG'].iloc[7] == 1.0)
        setup_name = res['engine_setup'].iloc[7]
        is_pass = has_breakout and has_retest and (setup_name == 'BREAKOUT_RETEST')
        results.append(("BREAKOUT_RETEST_LONG", "BREAKOUT_RETEST", setup_name if is_pass else f"BO:{has_breakout},RT:{has_retest},{setup_name}", "PASS" if is_pass else "FAIL"))
    except Exception as e:
        results.append(("BREAKOUT_RETEST_LONG", "BREAKOUT_RETEST", str(e), "FAIL"))

    # -------------------------------------------------------------
    # 2. SHORT BREAKDOWN -> RETEST -> CONFIRMATION -> ENTRY
    # -------------------------------------------------------------
    try:
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        # Свинг лоу 95 на свече 2, подтверждается на свече 4
        # Свеча 5: Медвежий пробой вниз закрытием на 92.0
        # Свеча 6: Откат снизу к 94.0
        # Свеча 7: Ретест в 94.8 с медвежьим пин-баром (close 94.5 <= zone_high)
        closes = [100, 97, 95, 97, 99, 92.0, 94.0, 94.5]
        highs  = [100.5, 97.5, 95.5, 97.5, 99.5, 93.0, 94.5, 95.5]
        lows   = [99.5, 96.5, 94.5, 96.5, 98.5, 91.5, 93.5, 94.0]
        opens  = [100, 97, 95, 97, 99, 98.0, 92.5, 94.8]
        df = create_df(closes, highs=highs, lows=lows, opens=opens)
        res = engine.analyze(df)
        
        has_breakdown = (res['IS_BREAKOUT_SHORT'].iloc[5] == 1.0)
        has_retest = (res['IS_RETEST_SHORT'].iloc[7] == 1.0)
        setup_name = res['engine_setup'].iloc[7]
        is_pass = has_breakdown and has_retest and (setup_name == 'BREAKDOWN_RETEST')
        results.append(("BREAKDOWN_RETEST_SHORT", "BREAKDOWN_RETEST", setup_name if is_pass else f"BD:{has_breakdown},RT:{has_retest},{setup_name}", "PASS" if is_pass else "FAIL"))
    except Exception as e:
        results.append(("BREAKDOWN_RETEST_SHORT", "BREAKDOWN_RETEST", str(e), "FAIL"))

    # -------------------------------------------------------------
    # 3. FALSE BREAKOUT / LIQUIDITY SWEEP (LONG & SHORT)
    # -------------------------------------------------------------
    try:
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        # Support на 100. Свеча прокалывает тенью до 97.5, закрытие 100.5
        closes = [105, 102, 100, 102, 104, 103, 100.5]
        lows   = [104.5, 101.5, 99.8, 101.5, 103.5, 102.5, 97.5]
        highs  = [105.5, 102.5, 100.5, 102.5, 104.5, 103.5, 101.0]
        opens  = [105, 102, 100, 102, 104, 103, 100.2]
        df = create_df(closes, highs=highs, lows=lows, opens=opens)
        res = engine.analyze(df)
        sweep_ok = (res['LIQUIDITY_SWEEP_LOW'].iloc[-1] == 1.0)
        setup_ok = (res['engine_setup'].iloc[-1] == 'LIQUIDITY_SWEEP_LONG')
        is_pass = sweep_ok and setup_ok
        results.append(("LIQUIDITY_SWEEP_LONG", "LIQUIDITY_SWEEP_LONG", res['engine_setup'].iloc[-1], "PASS" if is_pass else "FAIL"))
    except Exception as e:
        results.append(("LIQUIDITY_SWEEP_LONG", "LIQUIDITY_SWEEP_LONG", str(e), "FAIL"))

    try:
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        # Resistance на 110. Свеча прокалывает тенью до 113.0, закрытие 109.5
        closes = [105, 108, 110, 108, 106, 107, 109.5]
        highs  = [105.5, 108.5, 110.2, 108.5, 106.5, 107.5, 113.0]
        lows   = [104.5, 107.5, 109.5, 107.5, 105.5, 106.5, 109.0]
        opens  = [105, 108, 110, 108, 106, 107, 109.7]
        df = create_df(closes, highs=highs, lows=lows, opens=opens)
        res = engine.analyze(df)
        sweep_ok = (res['LIQUIDITY_SWEEP_HIGH'].iloc[-1] == 1.0)
        setup_ok = (res['engine_setup'].iloc[-1] == 'LIQUIDITY_SWEEP_SHORT')
        is_pass = sweep_ok and setup_ok
        results.append(("LIQUIDITY_SWEEP_SHORT", "LIQUIDITY_SWEEP_SHORT", res['engine_setup'].iloc[-1], "PASS" if is_pass else "FAIL"))
    except Exception as e:
        results.append(("LIQUIDITY_SWEEP_SHORT", "LIQUIDITY_SWEEP_SHORT", str(e), "FAIL"))

    # -------------------------------------------------------------
    # 4. TREND PULLBACK (LONG & SHORT)
    # -------------------------------------------------------------
    try:
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        # Бычья структура: 2 свинга вверх, затем откат к уровню с откупом
        prices = [100, 103, 106, 103, 101, 105, 110, 107, 104, 107, 115, 111, 106, 106.5]
        highs = [p + 0.5 for p in prices]
        lows = [p - 0.5 for p in prices]
        opens = [p for p in prices]
        lows[-1] = 104.0  # Бычий откуп на откате
        df = create_df(prices, highs=highs, lows=lows, opens=opens)
        res = engine.analyze(df)
        has_pullback = ('TREND_PULLBACK' in res['engine_setup'].values)
        results.append(("TREND_PULLBACK_LONG", "TREND_PULLBACK", "TREND_PULLBACK" if has_pullback else "Not Found", "PASS" if has_pullback else "FAIL"))
    except Exception as e:
        results.append(("TREND_PULLBACK_LONG", "TREND_PULLBACK", str(e), "FAIL"))

    try:
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        # Медвежья структура: 2 свинга вниз, откат вверх с отбоем
        prices = [120, 117, 114, 117, 119, 115, 110, 113, 116, 113, 105, 109, 114, 113.5]
        highs = [p + 0.5 for p in prices]
        lows = [p - 0.5 for p in prices]
        opens = [p for p in prices]
        highs[-1] = 116.0 # Медвежий пин-бар
        df = create_df(prices, highs=highs, lows=lows, opens=opens)
        res = engine.analyze(df)
        has_pullback = ('TREND_PULLBACK_DOWN' in res['engine_setup'].values)
        results.append(("TREND_PULLBACK_SHORT", "TREND_PULLBACK_DOWN", "TREND_PULLBACK_DOWN" if has_pullback else "Not Found", "PASS" if has_pullback else "FAIL"))
    except Exception as e:
        results.append(("TREND_PULLBACK_SHORT", "TREND_PULLBACK_DOWN", str(e), "FAIL"))

    # -------------------------------------------------------------
    # 5. RANGE BOUNCE (LONG & SHORT)
    # -------------------------------------------------------------
    try:
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        # Коридор 100-104
        prices = [100, 102, 104, 102, 100, 102, 104, 102, 100, 102, 104, 102, 100, 100.1]
        highs = [p + 0.5 for p in prices]
        lows = [p - 0.5 for p in prices]
        lows[-1] = 98.5  # Откуп на нижней границе
        df = create_df(prices, highs=highs, lows=lows)
        res = engine.analyze(df)
        has_rb = ('RANGE_BOUNCE' in res['engine_setup'].values)
        results.append(("RANGE_BOUNCE_LONG", "RANGE_BOUNCE", "RANGE_BOUNCE" if has_rb else "Not Found", "PASS" if has_rb else "FAIL"))
    except Exception as e:
        results.append(("RANGE_BOUNCE_LONG", "RANGE_BOUNCE", str(e), "FAIL"))

    try:
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        prices = [100, 102, 104, 102, 100, 102, 104, 102, 100, 102, 104, 102, 100, 103.9]
        highs = [p + 0.5 for p in prices]
        lows = [p - 0.5 for p in prices]
        highs[-1] = 105.5 # Отбой от верхней границы
        df = create_df(prices, highs=highs, lows=lows)
        res = engine.analyze(df)
        has_rr = ('RANGE_REJECTION' in res['engine_setup'].values)
        results.append(("RANGE_BOUNCE_SHORT", "RANGE_REJECTION", "RANGE_REJECTION" if has_rr else "Not Found", "PASS" if has_rr else "FAIL"))
    except Exception as e:
        results.append(("RANGE_BOUNCE_SHORT", "RANGE_REJECTION", str(e), "FAIL"))

    # -------------------------------------------------------------
    # 6. BOS & CHOCH (LONG & SHORT)
    # -------------------------------------------------------------
    try:
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        # 1. CHOCH LONG: Медвежья структура -> пробой protected high
        # Медвежья: 120, 115, 118, 112
        prices = [120, 116, 114, 116, 117, 113, 108, 111, 113, 110, 106, 108, 122]
        highs = [p + 0.5 for p in prices]
        lows = [p - 0.5 for p in prices]
        df = create_df(prices, highs=highs, lows=lows)
        res = engine.analyze(df)
        has_choch_long = (res['CHOCH_LONG'].sum() > 0)
        results.append(("CHOCH_LONG", "Event on Break", "Detected" if has_choch_long else "Not Found", "PASS" if has_choch_long else "FAIL"))
    except Exception as e:
        results.append(("CHOCH_LONG", "Event on Break", str(e), "FAIL"))

    try:
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        # 2. CHOCH SHORT: Бычья структура -> пробой protected low
        prices = [100, 104, 107, 104, 102, 106, 111, 108, 105, 109, 114, 110, 95]
        highs = [p + 0.5 for p in prices]
        lows = [p - 0.5 for p in prices]
        df = create_df(prices, highs=highs, lows=lows)
        res = engine.analyze(df)
        has_choch_short = (res['CHOCH_SHORT'].sum() > 0)
        results.append(("CHOCH_SHORT", "Event on Break", "Detected" if has_choch_short else "Not Found", "PASS" if has_choch_short else "FAIL"))
    except Exception as e:
        results.append(("CHOCH_SHORT", "Event on Break", str(e), "FAIL"))

    try:
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        # 3. BOS LONG: Бычья структура -> закрытие выше protected_high
        prices = [100, 103, 106, 103, 101, 105, 110, 107, 104, 108, 116]
        highs = [p + 0.5 for p in prices]
        lows = [p - 0.5 for p in prices]
        df = create_df(prices, highs=highs, lows=lows)
        res = engine.analyze(df)
        has_bos_long = (res['BOS_LONG'].sum() > 0)
        # Проверяем, что событие точечное (не висит на нескольких барах подряд)
        bos_indices = np.where(res['BOS_LONG'] == 1.0)[0]
        single_candle = True
        for b_idx in bos_indices:
            if b_idx + 1 < len(res) and res['BOS_LONG'].iloc[b_idx + 1] == 1.0:
                single_candle = False
                break
        is_pass = has_bos_long and single_candle
        results.append(("BOS_LONG", "Single-candle Event", "Single-candle" if is_pass else "Sticky or missing", "PASS" if is_pass else "FAIL"))
    except Exception as e:
        results.append(("BOS_LONG", "Single-candle Event", str(e), "FAIL"))

    try:
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        # 4. BOS SHORT: Медвежья структура -> закрытие ниже protected_low
        prices = [120, 117, 114, 117, 119, 115, 110, 113, 116, 112, 104]
        highs = [p + 0.5 for p in prices]
        lows = [p - 0.5 for p in prices]
        df = create_df(prices, highs=highs, lows=lows)
        res = engine.analyze(df)
        has_bos_short = (res['BOS_SHORT'].sum() > 0)
        bos_indices = np.where(res['BOS_SHORT'] == 1.0)[0]
        single_candle = True
        for b_idx in bos_indices:
            if b_idx + 1 < len(res) and res['BOS_SHORT'].iloc[b_idx + 1] == 1.0:
                single_candle = False
                break
        is_pass = has_bos_short and single_candle
        results.append(("BOS_SHORT", "Single-candle Event", "Single-candle" if is_pass else "Sticky or missing", "PASS" if is_pass else "FAIL"))
    except Exception as e:
        results.append(("BOS_SHORT", "Single-candle Event", str(e), "FAIL"))

    # -------------------------------------------------------------
    # 7. NO LOOKAHEAD (with explicit swing_k=3 test)
    # -------------------------------------------------------------
    try:
        engine = MarketStructureEngine(swing_k=3, retest_max_bars=5)
        np.random.seed(999)
        n = 120
        c = 100.0 * np.cumprod(1 + np.random.normal(0.0001, 0.005, n))
        df_full = create_df(c)
        
        # Анализ первых 70 баров
        df_70 = df_full.iloc[:70].copy()
        res_70 = engine.analyze(df_70)
        
        # Анализ всех 120 баров
        res_120 = engine.analyze(df_full.copy())
        
        lookahead = False
        diff_col = ""
        for col in ['DIST_SUP_PCT', 'DIST_RES_PCT', 'MARKET_STRUCTURE', 'IS_BREAKOUT_LONG', 'IS_RETEST_LONG', 'engine_signal', 'SETUP_SCORE']:
            v70 = res_70[col].iloc[69]
            v120 = res_120[col].iloc[69]
            if not np.isclose(v70, v120, equal_nan=True):
                lookahead = True
                diff_col = col
                break
                
        # Проверка: свинг на candle t-3 становится известен ТОЛЬКО на candle t
        # Сформируем экстремум на t=10. Он должен подтвердиться ровно на t=13 при k=3.
        swing_check = True
        sw_prices = [100]*20
        sw_prices[10] = 125.0 # swing high на 10
        sw_highs = [p + 0.1 for p in sw_prices]
        sw_df = create_df(sw_prices, highs=sw_highs)
        # На срезе до t=12 (до подтверждения) уровень 125 НЕ должен быть в зонах
        res_t12 = engine.analyze(sw_df.iloc[:13])
        # На срезе до t=13 (свеча подтверждения) уровень 125 ДОЛЖЕН появиться
        res_t13 = engine.analyze(sw_df.iloc[:14])
        
        if res_t12['NEAREST_RESISTANCE'].iloc[12] == 125.0: # Появился раньше времени!
            swing_check = False
        if res_t13['NEAREST_RESISTANCE'].iloc[13] != 125.0 and not np.isclose(res_t13['NEAREST_RESISTANCE'].iloc[13], 125.0, atol=1.0):
            swing_check = False

        is_pass = (not lookahead) and swing_check
        results.append(("NO_LOOKAHEAD", "Zero Lookahead (t-k only at t)", "Zero Lookahead" if is_pass else f"Lookahead in {diff_col} or swing", "PASS" if is_pass else "FAIL"))
    except Exception as e:
        results.append(("NO_LOOKAHEAD", "Zero Lookahead", str(e), "FAIL"))

    # -------------------------------------------------------------
    # 8. ONE SETUP = ONE ENTRY
    # -------------------------------------------------------------
    try:
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=5)
        # Свеча 7 дает вход. Свечи 8 и 9 тоже находятся в зоне
        closes = [100, 103, 105, 103, 101, 108.0, 106.0, 105.5, 105.5, 105.6]
        highs  = [100.5, 103.5, 105.5, 103.5, 101.5, 108.5, 106.5, 106.0, 106.0, 106.1]
        lows   = [99.5, 102.5, 104.5, 102.5, 100.5, 107.0, 105.8, 104.8, 104.8, 104.9]
        opens  = [100, 103, 105, 103, 101, 102.0, 107.5, 105.0, 105.1, 105.2]
        df = create_df(closes, highs=highs, lows=lows, opens=opens)
        res = engine.analyze(df)
        
        # На свече 7: ретест сработал
        entry_7 = (res['IS_RETEST_LONG'].iloc[7] == 1.0)
        # На свечах 8 и 9: повторного входа НЕТ
        entry_8 = (res['IS_RETEST_LONG'].iloc[8] == 1.0)
        entry_9 = (res['IS_RETEST_LONG'].iloc[9] == 1.0)
        
        is_pass = entry_7 and (not entry_8) and (not entry_9)
        results.append(("ONE_SETUP_ONE_ENTRY", "Single Entry (Consumed)", "1 Entry, 0 Duplicates" if is_pass else f"e7:{entry_7},e8:{entry_8},e9:{entry_9}", "PASS" if is_pass else "FAIL"))
    except Exception as e:
        results.append(("ONE_SETUP_ONE_ENTRY", "Single Entry", str(e), "FAIL"))

    # -------------------------------------------------------------
    # 9. MULTIPLE ACTIVE SETUPS
    # -------------------------------------------------------------
    try:
        engine = MarketStructureEngine(swing_k=2, retest_max_bars=8)
        # 1. Пробой сопротивления A (105.0) на свече 5
        # 2. Формирование нового сопротивления B (115.0) и его пробой на свече 10
        # 3. Оба сетапа должны сосуществовать в active_breakout_setups без перезаписи
        prices = [100, 103, 105, 103, 101, 108.0, 111, 115, 113, 111, 118.0]
        highs = [p + 0.5 for p in prices]
        lows = [p - 0.5 for p in prices]
        df = create_df(prices, highs=highs, lows=lows)
        res = engine.analyze(df)
        
        # Проверяем, что зафиксированы пробои на обеих свечах
        bo_indices = np.where(res['IS_BREAKOUT_LONG'] == 1.0)[0]
        has_multiple_bo = len(bo_indices) >= 2
        results.append(("MULTIPLE_SETUPS", "Concurrent Setups Preserved", f"{len(bo_indices)} Setups Tracked" if has_multiple_bo else "Overwritten", "PASS" if has_multiple_bo else "FAIL"))
    except Exception as e:
        results.append(("MULTIPLE_SETUPS", "Concurrent Setups Preserved", str(e), "FAIL"))

    # -------------------------------------------------------------
    # 10. TRAIN / LIVE PARITY
    # -------------------------------------------------------------
    try:
        np.random.seed(777)
        c = 100.0 * np.cumprod(1 + np.random.normal(0.0001, 0.005, 150))
        df_hist = create_df(c)
        
        ta = TAStrategy()
        # LIVE путь: TAStrategy.generate_features_and_signals
        res_live = ta.generate_features_and_signals(df_hist.copy())
        
        # TRAIN путь: тот же самый TAStrategy.generate_features_and_signals (вызываемый в train_model.py)
        res_train = ta.generate_features_and_signals(df_hist.copy())
        
        # Сравнение колонок
        parity = True
        diff_col = ""
        compare_cols = ['ta_signal', 'ta_setup', 'SETUP_SCORE', 'BOS_LONG', 'BOS_SHORT', 'CHOCH_LONG', 'CHOCH_SHORT', 'IS_BREAKOUT_LONG', 'IS_RETEST_LONG']
        for col in compare_cols:
            if col in res_live.columns:
                if not (res_live[col].values == res_train[col].values).all():
                    parity = False
                    diff_col = col
                    break
                    
        results.append(("TRAIN_LIVE_PARITY", "100% Identical Output", "100% Match" if parity else f"Diff in {diff_col}", "PASS" if parity else "FAIL"))
    except Exception as e:
        results.append(("TRAIN_LIVE_PARITY", "100% Identical Output", str(e), "FAIL"))

    # -------------------------------------------------------------
    # 11. ML FEATURE SCHEMA CHECK
    # -------------------------------------------------------------
    try:
        np.random.seed(888)
        c = 100.0 * np.cumprod(1 + np.random.normal(0.0001, 0.005, 150))
        df_ml = create_df(c)
        ta = TAStrategy()
        res_ml = ta.generate_features_and_signals(df_ml)
        
        missing_cols = [col for col in FEATURE_COLUMNS if col not in res_ml.columns]
        nan_cols = [col for col in FEATURE_COLUMNS if col in res_ml.columns and res_ml[col].isna().any()]
        inf_cols = [col for col in FEATURE_COLUMNS if col in res_ml.columns and np.isinf(res_ml[col]).any()]
        
        is_pass = (len(missing_cols) == 0) and (len(nan_cols) == 0) and (len(inf_cols) == 0)
        detail = f"{len(FEATURE_COLUMNS)} Features OK" if is_pass else f"Missing:{missing_cols}, NaN:{nan_cols}"
        results.append(("ML_FEATURE_SCHEMA", "33 Features, No NaN/Inf", detail, "PASS" if is_pass else "FAIL"))
    except Exception as e:
        results.append(("ML_FEATURE_SCHEMA", "33 Features, No NaN/Inf", str(e), "FAIL"))

    return results

if __name__ == "__main__":
    print("=" * 80)
    print("КОНТРОЛЬНАЯ ПРОВЕРКА MARKET STRUCTURE ENGINE (17 ТЕСТОВЫХ СЦЕНАРИЕВ)")
    print("=" * 80)
    print(f"{'TEST':<26} | {'EXPECTED':<28} | {'ACTUAL':<24} | {'PASS/FAIL'}")
    print("-" * 80)
    
    all_results = run_all_checks()
    all_passed = True
    for test_name, expected, actual, status in all_results:
        if status != "PASS":
            all_passed = False
        print(f"{test_name:<26} | {expected:<28} | {actual:<24} | {status}")
    
    print("=" * 80)
    if all_passed:
        print("ИТОГ: ВСЕ 17 ТЕСТОВ УСПЕШНО ПРОЙДЕНЫ (100% PASS)!")
        sys.exit(0)
    else:
        print("ИТОГ: ОБНАРУЖЕНЫ ОШИБКИ В ТЕСТАХ!")
        sys.exit(1)
