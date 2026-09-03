import numpy as np
import pandas as pd

def calculate_candle_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Рассчитывает свечные характеристики (тени, тела, пин-бары/отторжения).
    """
    data = df.copy()
    high = data['high'].values
    low = data['low'].values
    close = data['close'].values
    open_p = data['open'].values

    total_range = high - low
    total_range_safe = np.where(total_range <= 0, 1e-8, total_range)

    body = np.abs(close - open_p)
    upper_wick = high - np.maximum(close, open_p)
    lower_wick = np.minimum(close, open_p) - low

    data['WICK_UPPER_RATIO'] = upper_wick / total_range_safe
    data['WICK_LOWER_RATIO'] = lower_wick / total_range_safe
    data['BODY_RATIO'] = body / total_range_safe

    # Бычье отторжение (Пин-бар с длинной тенью снизу, продавцов откупили)
    data['BULLISH_REJECTION'] = (
        (data['WICK_LOWER_RATIO'] >= 0.40) & 
        (lower_wick >= 1.3 * body)
    ).astype(int)

    # Медвежье отторжение (Пин-бар с длинной тенью сверху, покупателей задавили)
    data['BEARISH_REJECTION'] = (
        (data['WICK_UPPER_RATIO'] >= 0.40) & 
        (upper_wick >= 1.3 * body)
    ).astype(int)

    return data


def calculate_market_structure(df: pd.DataFrame, swing_k: int = 3) -> pd.DataFrame:
    """
    Определяет уровни поддержки и сопротивления на основе подтвержденных свингов (фракталов)
    без заглядывания в будущее (Zero Lookahead Bias).
    
    Для свечи t используются только свинги, подтвержденные на или до момента t.
    """
    data = df.copy()
    n = len(data)
    
    highs = data['high'].values
    lows = data['low'].values
    closes = data['close'].values

    # Массивы для результатов
    nearest_sup = np.zeros(n)
    nearest_res = np.zeros(n)
    dist_sup_pct = np.zeros(n)
    dist_res_pct = np.zeros(n)
    market_structure = np.zeros(n)
    is_breakout_long = np.zeros(n)
    is_breakout_short = np.zeros(n)
    is_retest_long = np.zeros(n)
    is_retest_short = np.zeros(n)

    # Список подтвержденных уровней
    confirmed_swing_highs = [] # (index, price)
    confirmed_swing_lows = []  # (index, price)

    for i in range(n):
        # Проверяем, подтвердился ли свинг в точке i - swing_k
        cand_idx = i - swing_k
        if cand_idx >= swing_k:
            cand_high = highs[cand_idx]
            cand_low = lows[cand_idx]

            # Проверка Swing High: cand_high строго выше соседей в окне [-swing_k, +swing_k]
            is_sh = True
            for offset in range(-swing_k, swing_k + 1):
                if offset != 0 and highs[cand_idx + offset] >= cand_high:
                    is_sh = False
                    break
            if is_sh:
                confirmed_swing_highs.append((cand_idx, cand_high))
                # Ограничиваем историю последних 50 свингов для скорости
                if len(confirmed_swing_highs) > 50:
                    confirmed_swing_highs.pop(0)

            # Проверка Swing Low: cand_low строго ниже соседей в окне [-swing_k, +swing_k]
            is_sl = True
            for offset in range(-swing_k, swing_k + 1):
                if offset != 0 and lows[cand_idx + offset] <= cand_low:
                    is_sl = False
                    break
            if is_sl:
                confirmed_swing_lows.append((cand_idx, cand_low))
                if len(confirmed_swing_lows) > 50:
                    confirmed_swing_lows.pop(0)

        curr_c = closes[i]

        # 1. Поиск ближайшей поддержки (Swing Low ниже текущей цены)
        valid_sups = [p for _, p in confirmed_swing_lows if p < curr_c]
        if valid_sups:
            best_sup = max(valid_sups)
        else:
            best_sup = curr_c * 0.95 # Дефолт: 5% ниже
        nearest_sup[i] = best_sup
        dist_sup_pct[i] = (curr_c - best_sup) / curr_c

        # 2. Поиск ближайшего сопротивления (Swing High выше текущей цены)
        valid_res = [p for _, p in confirmed_swing_highs if p > curr_c]
        if valid_res:
            best_res = min(valid_res)
        else:
            best_res = curr_c * 1.05 # Дефолт: 5% выше
        nearest_res[i] = best_res
        dist_res_pct[i] = (best_res - curr_c) / curr_c

        # 3. Определение структуры рынка (Higher Highs / Higher Lows vs Lower Highs / Lower Lows)
        if len(confirmed_swing_highs) >= 2 and len(confirmed_swing_lows) >= 2:
            last_sh, prev_sh = confirmed_swing_highs[-1][1], confirmed_swing_highs[-2][1]
            last_sl, prev_sl = confirmed_swing_lows[-1][1], confirmed_swing_lows[-2][1]
            if last_sh > prev_sh and last_sl > prev_sl:
                market_structure[i] = 1.0 # Бычья структура (HH + HL)
            elif last_sh < prev_sh and last_sl < prev_sl:
                market_structure[i] = -1.0 # Медвежья структура (LH + LL)
            else:
                market_structure[i] = 0.0 # Смешанная / Боковик

        # 4. Пробой уровня (Breakout)
        if i >= 1 and len(confirmed_swing_highs) >= 1:
            recent_sh = confirmed_swing_highs[-1][1]
            if closes[i-1] <= recent_sh and curr_c > recent_sh:
                is_breakout_long[i] = 1.0

        if i >= 1 and len(confirmed_swing_lows) >= 1:
            recent_sl = confirmed_swing_lows[-1][1]
            if closes[i-1] >= recent_sl and curr_c < recent_sl:
                is_breakout_short[i] = 1.0

        # 5. Ретест уровня (Retest)
        # Был пробой 1-5 свечей назад, и сейчас цена вернулась к пробитому уровню в пределах 0.8%
        if i >= 2 and len(confirmed_swing_highs) >= 1:
            recent_sh = confirmed_swing_highs[-1][1]
            was_breakout = any(is_breakout_long[max(0, i-5):i] == 1.0)
            if was_breakout and abs(curr_c - recent_sh) / recent_sh <= 0.008 and curr_c >= recent_sh * 0.995:
                is_retest_long[i] = 1.0

        if i >= 2 and len(confirmed_swing_lows) >= 1:
            recent_sl = confirmed_swing_lows[-1][1]
            was_breakout = any(is_breakout_short[max(0, i-5):i] == 1.0)
            if was_breakout and abs(curr_c - recent_sl) / recent_sl <= 0.008 and curr_c <= recent_sl * 1.005:
                is_retest_short[i] = 1.0

    data['NEAREST_SUPPORT'] = nearest_sup
    data['NEAREST_RESISTANCE'] = nearest_res
    data['DIST_SUP_PCT'] = dist_sup_pct
    data['DIST_RES_PCT'] = dist_res_pct
    data['MARKET_STRUCTURE'] = market_structure
    data['IS_BREAKOUT_LONG'] = is_breakout_long
    data['IS_BREAKOUT_SHORT'] = is_breakout_short
    data['IS_RETEST_LONG'] = is_retest_long
    data['IS_RETEST_SHORT'] = is_retest_short

    return data


def enrich_with_market_structure(df: pd.DataFrame) -> pd.DataFrame:
    """
    Полное обогащение датафрейма свечными паттернами и рыночной структурой.
    """
    if df is None or df.empty:
        return df
    
    # 1. Свечные отторжения
    df_pats = calculate_candle_patterns(df)
    
    # 2. Уровни, свинги, пробои и ретесты
    df_struct = calculate_market_structure(df_pats, swing_k=3)
    
    return df_struct
