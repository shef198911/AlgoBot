import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from config import (
    SWING_K,
    SR_ZONE_ATR_MULTIPLIER,
    SR_MERGE_TOLERANCE_ATR,
    BREAKOUT_ATR_MULTIPLIER,
    MIN_BREAKOUT_PCT,
    RETEST_TOLERANCE_ATR,
    RETEST_MAX_BARS,
    INVALIDATION_ATR_MULTIPLIER,
    PINBAR_WICK_RATIO,
    ENGULFING_BODY_RATIO,
    SCORE_WEIGHT_BREAKOUT,
    SCORE_WEIGHT_RETEST,
    SCORE_WEIGHT_REJECTION,
    SCORE_WEIGHT_VOLUME,
    SCORE_WEIGHT_STRUCTURE,
    SCORE_WEIGHT_TREND,
    SCORE_WEIGHT_MOMENTUM,
    MIN_SETUP_SCORE,
    logger
)

class SRZone:
    """Зона поддержки или сопротивления с динамической шириной и счетчиком силы."""
    def __init__(self, price: float, atr: float, zone_type: str, candle_idx: int, volume: float = 1.0):
        self.center: float = price
        self.zone_type: str = zone_type # 'SUPPORT' or 'RESISTANCE'
        self.atr: float = max(atr, price * 0.001)
        half_width = (self.atr * SR_ZONE_ATR_MULTIPLIER) / 2.0
        self.high: float = price + half_width
        self.low: float = price - half_width
        self.touch_count: int = 1
        self.first_idx: int = candle_idx
        self.last_idx: int = candle_idx
        self.volume_weight: float = volume
        self.strength: float = 30.0 # Базовая сила при первом обнаружении

    def update_touch(self, price: float, atr: float, candle_idx: int, volume: float = 1.0):
        """Объединение близкого свинга в зону и увеличение силы уровня."""
        self.touch_count += 1
        self.last_idx = candle_idx
        self.atr = max(atr, price * 0.001)
        # Сдвигаем центр к средневзвешенному
        self.center = (self.center * (self.touch_count - 1) + price) / self.touch_count
        half_width = (self.atr * SR_ZONE_ATR_MULTIPLIER) / 2.0
        self.high = self.center + half_width
        self.low = self.center - half_width
        # Сила растет с каждым касанием (до 80) + бонус за объем
        touch_bonus = min(50.0, self.touch_count * 15.0)
        self.strength = min(100.0, 30.0 + touch_bonus)


class MarketStructureEngine:
    """
    Полнофункциональный движок рыночной структуры и Price Action.
    Работает без заглядывания в будущее (Zero Lookahead Bias).
    Один и тот же движок используется и в Live, и в Training (100% паритет).
    """
    def __init__(self, swing_k: Optional[int] = None, retest_max_bars: Optional[int] = None):
        self.swing_k = swing_k or SWING_K
        self.retest_max_bars = retest_max_bars or RETEST_MAX_BARS
        self.logger = logger.getChild("MarketStructureEngine")

    def calculate_candle_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Расчет свечных паттернов без заглядывания в будущее."""
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

        # 1. Пин-бары / Отторжения
        data['BULLISH_REJECTION'] = (
            (data['WICK_LOWER_RATIO'] >= PINBAR_WICK_RATIO) & 
            (lower_wick >= 1.3 * body)
        ).astype(int)

        data['BEARISH_REJECTION'] = (
            (data['WICK_UPPER_RATIO'] >= PINBAR_WICK_RATIO) & 
            (upper_wick >= 1.3 * body)
        ).astype(int)

        data['PIN_BAR'] = (data['BULLISH_REJECTION'] | data['BEARISH_REJECTION']).astype(int)

        # 2. Поглощения (Engulfing)
        n = len(data)
        bull_engulf = np.zeros(n)
        bear_engulf = np.zeros(n)
        inside_bar = np.zeros(n)
        outside_bar = np.zeros(n)

        for i in range(1, n):
            prev_body = body[i-1]
            curr_body = body[i]
            # Бычье поглощение: прошлая свеча красная, текущая зеленая, тело больше
            if close[i-1] < open_p[i-1] and close[i] > open_p[i]:
                if curr_body >= ENGULFING_BODY_RATIO * prev_body and close[i] >= open_p[i-1]:
                    bull_engulf[i] = 1.0

            # Медвежье поглощение: прошлая зеленая, текущая красная, тело больше
            if close[i-1] > open_p[i-1] and close[i] < open_p[i]:
                if curr_body >= ENGULFING_BODY_RATIO * prev_body and close[i] <= open_p[i-1]:
                    bear_engulf[i] = 1.0

            # Inside / Outside Bar
            if high[i] <= high[i-1] and low[i] >= low[i-1]:
                inside_bar[i] = 1.0
            if high[i] > high[i-1] and low[i] < low[i-1]:
                outside_bar[i] = 1.0

        data['BULLISH_ENGULFING'] = bull_engulf
        data['BEARISH_ENGULFING'] = bear_engulf
        data['INSIDE_BAR'] = inside_bar
        data['OUTSIDE_BAR'] = outside_bar

        return data

    def calculate_setup_score(
        self,
        has_breakout: bool,
        has_retest: bool,
        has_rejection: bool,
        vol_ratio: float,
        structure_aligned: bool,
        trend_aligned: bool,
        momentum_ok: bool
    ) -> float:
        """
        Расчет взвешенной силы сетапа (0..100) по весам из config.py.
        """
        score = 0.0
        if has_breakout:
            score += SCORE_WEIGHT_BREAKOUT
        if has_retest:
            score += SCORE_WEIGHT_RETEST
        if has_rejection:
            score += SCORE_WEIGHT_REJECTION
        if vol_ratio >= 1.2:
            score += SCORE_WEIGHT_VOLUME
        elif vol_ratio >= 1.0:
            score += SCORE_WEIGHT_VOLUME * 0.6
        if structure_aligned:
            score += SCORE_WEIGHT_STRUCTURE
        if trend_aligned:
            score += SCORE_WEIGHT_TREND
        if momentum_ok:
            score += SCORE_WEIGHT_MOMENTUM
        return min(100.0, score)

    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Главная точка входа движка: анализирует рынок и возвращает датафрейм
        с уровнями, зонами, структурой, сетапами и машиной состояний.
        """
        if df is None or df.empty:
            return df

        # 1. Расчет ATR если он еще не рассчитан
        data = df.copy()
        if 'ATRr' not in data.columns:
            if len(data) >= 14:
                from ta.volatility import AverageTrueRange
                data['ATRr'] = AverageTrueRange(
                    high=data['high'], low=data['low'], close=data['close'], window=14
                ).average_true_range().fillna(data['close'] * 0.01)
            else:
                tr = np.maximum(data['high'] - data['low'], data['close'] * 0.005)
                data['ATRr'] = tr

        # 2. Свечные паттерны
        data = self.calculate_candle_patterns(data)

        # 3. Скользящий средний объем для качества пробоев
        if 'volume' in data.columns and data['volume'].sum() > 0:
            mean_vol = data['volume'].rolling(window=20).mean().fillna(data['volume'])
            vol_ratio_arr = (data['volume'] / np.where(mean_vol <= 0, 1e-8, mean_vol)).fillna(1.0).values
        else:
            vol_ratio_arr = np.ones(len(data))

        n = len(data)
        highs = data['high'].values
        lows = data['low'].values
        closes = data['close'].values
        opens = data['open'].values
        atrs = data['ATRr'].values
        bull_rej = data['BULLISH_REJECTION'].values
        bear_rej = data['BEARISH_REJECTION'].values
        bull_eng = data['BULLISH_ENGULFING'].values
        bear_eng = data['BEARISH_ENGULFING'].values

        # Выходные массивы
        nearest_sup_arr = np.zeros(n)
        nearest_res_arr = np.zeros(n)
        dist_sup_pct_arr = np.zeros(n)
        dist_res_pct_arr = np.zeros(n)
        sr_strength_arr = np.zeros(n)
        market_structure_arr = np.zeros(n)
        bos_long_arr = np.zeros(n)
        bos_short_arr = np.zeros(n)
        choch_long_arr = np.zeros(n)
        choch_short_arr = np.zeros(n)
        breakout_strength_arr = np.zeros(n)
        breakout_vol_ratio_arr = np.zeros(n)
        is_breakout_long_arr = np.zeros(n)
        is_breakout_short_arr = np.zeros(n)
        is_retest_long_arr = np.zeros(n)
        is_retest_short_arr = np.zeros(n)
        sweep_high_arr = np.zeros(n)
        sweep_low_arr = np.zeros(n)
        setup_score_arr = np.zeros(n)
        engine_setup_arr = ["None"] * n
        engine_signal_arr = np.zeros(n)

        # Активные структуры
        active_support_zones: List[SRZone] = []
        active_resistance_zones: List[SRZone] = []

        confirmed_swings: List[Tuple[str, int, float]] = [] # ('HIGH'|'LOW', candle_idx, price)
        
        # State Machine для Breakout & Retest
        # setup = { 'id': str, 'direction': 'LONG'|'SHORT', 'zone': SRZone, 'breakout_idx': int, 'breakout_strength': float, 'breakout_vol': float, 'bars_waiting': int, 'state': str }
        active_breakout_setup: Optional[Dict] = None
        consumed_setup_ids = set()

        k = self.swing_k

        for i in range(n):
            curr_c = closes[i]
            curr_h = highs[i]
            curr_l = lows[i]
            curr_atr = atrs[i] if atrs[i] > 0 else curr_c * 0.01
            curr_vol_ratio = vol_ratio_arr[i]

            # --- A. ДЕТЕКЦИЯ СВИНГОВ (ZERO LOOKAHEAD) ---
            # Свинг в свече cand_idx подтверждается только на свече i, когда появилось k свечей справа
            cand_idx = i - k
            if cand_idx >= k:
                cand_h = highs[cand_idx]
                cand_l = lows[cand_idx]
                cand_atr = atrs[cand_idx]

                # Проверка Swing High: строго выше всех соседей в окне [-k, +k]
                is_sh = True
                for offset in range(-k, k + 1):
                    if offset != 0 and highs[cand_idx + offset] >= cand_h:
                        is_sh = False
                        break
                if is_sh:
                    confirmed_swings.append(('HIGH', cand_idx, cand_h))
                    # Кластеризация в зоны сопротивления
                    merged = False
                    merge_tol = cand_atr * SR_MERGE_TOLERANCE_ATR
                    for zone in active_resistance_zones:
                        if abs(zone.center - cand_h) <= merge_tol:
                            zone.update_touch(cand_h, cand_atr, cand_idx)
                            merged = True
                            break
                    if not merged:
                        active_resistance_zones.append(SRZone(cand_h, cand_atr, 'RESISTANCE', cand_idx))

                # Проверка Swing Low: строго ниже всех соседей в окне [-k, +k]
                is_sl = True
                for offset in range(-k, k + 1):
                    if offset != 0 and lows[cand_idx + offset] <= cand_l:
                        is_sl = False
                        break
                if is_sl:
                    confirmed_swings.append(('LOW', cand_idx, cand_l))
                    # Кластеризация в зоны поддержки
                    merged = False
                    merge_tol = cand_atr * SR_MERGE_TOLERANCE_ATR
                    for zone in active_support_zones:
                        if abs(zone.center - cand_l) <= merge_tol:
                            zone.update_touch(cand_l, cand_atr, cand_idx)
                            merged = True
                            break
                    if not merged:
                        active_support_zones.append(SRZone(cand_l, cand_atr, 'SUPPORT', cand_idx))

                # Ограничиваем список зон последними 20
                if len(active_resistance_zones) > 20:
                    active_resistance_zones.pop(0)
                if len(active_support_zones) > 20:
                    active_support_zones.pop(0)
                if len(confirmed_swings) > 40:
                    confirmed_swings.pop(0)

            # --- B. ПОИСК АКТИВНЫХ ЗОН S/R И РАССТОЯНИЙ ---
            valid_sups = [z for z in active_support_zones if z.high < curr_c]
            if valid_sups:
                best_sup_zone = max(valid_sups, key=lambda z: z.high)
                nearest_sup = best_sup_zone.high
                sup_dist = (curr_c - nearest_sup) / curr_c
                sup_strength = best_sup_zone.strength
            else:
                nearest_sup = curr_c * 0.95
                sup_dist = 0.05
                sup_strength = 20.0

            valid_res = [z for z in active_resistance_zones if z.low > curr_c]
            if valid_res:
                best_res_zone = min(valid_res, key=lambda z: z.low)
                nearest_res = best_res_zone.low
                res_dist = (nearest_res - curr_c) / curr_c
                res_strength = best_res_zone.strength
            else:
                nearest_res = curr_c * 1.05
                res_dist = 0.05
                res_strength = 20.0

            nearest_sup_arr[i] = nearest_sup
            nearest_res_arr[i] = nearest_res
            dist_sup_pct_arr[i] = max(0.0, sup_dist)
            dist_res_pct_arr[i] = max(0.0, res_dist)
            sr_strength_arr[i] = max(sup_strength, res_strength)

            # --- C. СТРУКТУРА РЫНКА (HH/HL vs LH/LL), BOS И CHOCH ---
            sh_list = [p for t, _, p in confirmed_swings if t == 'HIGH']
            sl_list = [p for t, _, p in confirmed_swings if t == 'LOW']

            curr_structure = 0.0
            if len(sh_list) >= 2 and len(sl_list) >= 2:
                last_sh, prev_sh = sh_list[-1], sh_list[-2]
                last_sl, prev_sl = sl_list[-1], sl_list[-2]
                if last_sh > prev_sh and last_sl > prev_sl:
                    curr_structure = 1.0 # Bullish (HH + HL)
                elif last_sh < prev_sh and last_sl < prev_sl:
                    curr_structure = -1.0 # Bearish (LH + LL)

            market_structure_arr[i] = curr_structure

            # BOS & CHOCH детекция
            if i >= 1 and len(sh_list) >= 1 and len(sl_list) >= 1:
                last_sh = sh_list[-1]
                last_sl = sl_list[-1]

                # BOS LONG: закрытие выше предыдущего Swing High при бычьей структуре
                if curr_c > last_sh and closes[i-1] <= last_sh and curr_structure >= 0:
                    bos_long_arr[i] = 1.0

                # BOS SHORT: закрытие ниже предыдущего Swing Low при медвежьей структуре
                if curr_c < last_sl and closes[i-1] >= last_sl and curr_structure <= 0:
                    bos_short_arr[i] = 1.0

                # CHOCH LONG: закрытие выше Swing High при предшествующей медвежьей структуре (разворот)
                if curr_c > last_sh and closes[i-1] <= last_sh and curr_structure < 0:
                    choch_long_arr[i] = 1.0

                # CHOCH SHORT: закрытие ниже Swing Low при предшествующей бычьей структуре (разворот)
                if curr_c < last_sl and closes[i-1] >= last_sl and curr_structure > 0:
                    choch_short_arr[i] = 1.0

            # --- D. ЛОЖНЫЙ ПРОБОЙ / LIQUIDITY SWEEP ---
            # Прокол зоны тенью, но закрытие обратно внутри
            for z in active_resistance_zones:
                if curr_h > z.high and curr_c <= z.high:
                    sweep_high_arr[i] = 1.0
                    break
            for z in active_support_zones:
                if curr_l < z.low and curr_c >= z.low:
                    sweep_low_arr[i] = 1.0
                    break

            # --- E. ДЕТЕКЦИЯ ИСТИННОГО ПРОБОЯ (BREAKOUT) ---
            breakout_buf = max(curr_atr * BREAKOUT_ATR_MULTIPLIER, curr_c * MIN_BREAKOUT_PCT)
            
            # LONG Breakout: закрытие выше resistance zone + буфер
            detected_bo_long = False
            for z in active_resistance_zones:
                if i >= 1 and closes[i-1] <= z.high and curr_c > (z.high + breakout_buf):
                    detected_bo_long = True
                    is_breakout_long_arr[i] = 1.0
                    bo_str = (curr_c - z.high) / curr_atr
                    breakout_strength_arr[i] = bo_str
                    breakout_vol_ratio_arr[i] = curr_vol_ratio
                    setup_id = f"BO_LONG_{z.first_idx}_{z.center:.2f}"
                    if setup_id not in consumed_setup_ids:
                        active_breakout_setup = {
                            'id': setup_id,
                            'direction': 'LONG',
                            'level_center': z.center,
                            'zone_low': z.low,
                            'zone_high': z.high,
                            'breakout_idx': i,
                            'breakout_strength': bo_str,
                            'breakout_vol': curr_vol_ratio,
                            'bars_waiting': 0,
                            'state': 'WAITING_RETEST'
                        }
                    break

            # SHORT Breakdown: закрытие ниже support zone - буфер
            detected_bo_short = False
            for z in active_support_zones:
                if i >= 1 and closes[i-1] >= z.low and curr_c < (z.low - breakout_buf):
                    detected_bo_short = True
                    is_breakout_short_arr[i] = 1.0
                    bo_str = (z.low - curr_c) / curr_atr
                    breakout_strength_arr[i] = bo_str
                    breakout_vol_ratio_arr[i] = curr_vol_ratio
                    setup_id = f"BO_SHORT_{z.first_idx}_{z.center:.2f}"
                    if setup_id not in consumed_setup_ids:
                        active_breakout_setup = {
                            'id': setup_id,
                            'direction': 'SHORT',
                            'level_center': z.center,
                            'zone_low': z.low,
                            'zone_high': z.high,
                            'breakout_idx': i,
                            'breakout_strength': bo_str,
                            'breakout_vol': curr_vol_ratio,
                            'bars_waiting': 0,
                            'state': 'WAITING_RETEST'
                        }
                    break

            # --- F. STATE MACHINE ДЛЯ RETEST & ENTRY ---
            if active_breakout_setup is not None and not detected_bo_long and not detected_bo_short:
                active_breakout_setup['bars_waiting'] += 1
                bars_w = active_breakout_setup['bars_waiting']
                direction = active_breakout_setup['direction']
                z_high = active_breakout_setup['zone_high']
                z_low = active_breakout_setup['zone_low']

                # 1. Проверка таймаута
                if bars_w > self.retest_max_bars:
                    active_breakout_setup = None # EXPIRED

                # 2. Проверка инвалидации (пробитие уровня глубоко обратно)
                elif direction == 'LONG' and curr_c < (z_low - curr_atr * INVALIDATION_ATR_MULTIPLIER):
                    active_breakout_setup = None # INVALIDATED
                elif direction == 'SHORT' and curr_c > (z_high + curr_atr * INVALIDATION_ATR_MULTIPLIER):
                    active_breakout_setup = None # INVALIDATED

                # 3. Проверка взаимодействия с зоной (Retest)
                else:
                    retest_tol = curr_atr * RETEST_TOLERANCE_ATR
                    if direction == 'LONG':
                        # Цена вернулась в зону: low касается уровня, high удерживается
                        touch_zone = (curr_l <= z_high + retest_tol) and (curr_h >= z_low - curr_atr * 0.2)
                        if touch_zone:
                            active_breakout_setup['state'] = 'RETEST_DETECTED'
                            # Проверка подтверждения отскока / удержания (Hold confirmation)
                            is_confirmed = (curr_c >= z_low) and (bull_rej[i] or bull_eng[i] or curr_c > opens[i])
                            if is_confirmed:
                                is_retest_long_arr[i] = 1.0
                                score = self.calculate_setup_score(
                                    has_breakout=True,
                                    has_retest=True,
                                    has_rejection=bool(bull_rej[i] or bull_eng[i]),
                                    vol_ratio=active_breakout_setup['breakout_vol'],
                                    structure_aligned=(curr_structure >= 0),
                                    trend_aligned=True,
                                    momentum_ok=True
                                )
                                setup_score_arr[i] = score
                                engine_setup_arr[i] = "BREAKOUT_RETEST"
                                if score >= MIN_SETUP_SCORE:
                                    engine_signal_arr[i] = 1.0
                                # Помечаем как использованный сетап (Один сетап = один вход)
                                consumed_setup_ids.add(active_breakout_setup['id'])
                                active_breakout_setup = None

                    elif direction == 'SHORT':
                        touch_zone = (curr_h >= z_low - retest_tol) and (curr_l <= z_high + curr_atr * 0.2)
                        if touch_zone:
                            active_breakout_setup['state'] = 'RETEST_DETECTED'
                            is_confirmed = (curr_c <= z_high) and (bear_rej[i] or bear_eng[i] or curr_c < opens[i])
                            if is_confirmed:
                                is_retest_short_arr[i] = 1.0
                                score = self.calculate_setup_score(
                                    has_breakout=True,
                                    has_retest=True,
                                    has_rejection=bool(bear_rej[i] or bear_eng[i]),
                                    vol_ratio=active_breakout_setup['breakout_vol'],
                                    structure_aligned=(curr_structure <= 0),
                                    trend_aligned=True,
                                    momentum_ok=True
                                )
                                setup_score_arr[i] = score
                                engine_setup_arr[i] = "BREAKDOWN_RETEST"
                                if score >= MIN_SETUP_SCORE:
                                    engine_signal_arr[i] = -1.0
                                consumed_setup_ids.add(active_breakout_setup['id'])
                                active_breakout_setup = None

            # --- G. ДРУГИЕ СЕТАПЫ (SUPPORT BOUNCE, RESISTANCE REJECTION, TREND PULLBACK) ---
            if engine_signal_arr[i] == 0:
                # 1. Support Bounce
                if dist_sup_pct_arr[i] <= (curr_atr * 0.8 / curr_c) and (bull_rej[i] or bull_eng[i]):
                    score = self.calculate_setup_score(
                        has_breakout=False,
                        has_retest=True, # Тест поддержки
                        has_rejection=True,
                        vol_ratio=curr_vol_ratio,
                        structure_aligned=(curr_structure >= 0),
                        trend_aligned=True,
                        momentum_ok=True
                    )
                    setup_score_arr[i] = score
                    engine_setup_arr[i] = "SUPPORT_BOUNCE"
                    if score >= MIN_SETUP_SCORE:
                        engine_signal_arr[i] = 1.0

                # 2. Resistance Rejection
                elif dist_res_pct_arr[i] <= (curr_atr * 0.8 / curr_c) and (bear_rej[i] or bear_eng[i]):
                    score = self.calculate_setup_score(
                        has_breakout=False,
                        has_retest=True,
                        has_rejection=True,
                        vol_ratio=curr_vol_ratio,
                        structure_aligned=(curr_structure <= 0),
                        trend_aligned=True,
                        momentum_ok=True
                    )
                    setup_score_arr[i] = score
                    engine_setup_arr[i] = "RESISTANCE_REJECTION"
                    if score >= MIN_SETUP_SCORE:
                        engine_signal_arr[i] = -1.0

                # 3. Liquidity Sweep Reversal
                elif sweep_low_arr[i] and (bull_rej[i] or bull_eng[i]):
                    score = self.calculate_setup_score(
                        has_breakout=False,
                        has_retest=True,
                        has_rejection=True,
                        vol_ratio=curr_vol_ratio,
                        structure_aligned=True,
                        trend_aligned=True,
                        momentum_ok=True
                    )
                    setup_score_arr[i] = score
                    engine_setup_arr[i] = "LIQUIDITY_SWEEP_LONG"
                    if score >= MIN_SETUP_SCORE:
                        engine_signal_arr[i] = 1.0

                elif sweep_high_arr[i] and (bear_rej[i] or bear_eng[i]):
                    score = self.calculate_setup_score(
                        has_breakout=False,
                        has_retest=True,
                        has_rejection=True,
                        vol_ratio=curr_vol_ratio,
                        structure_aligned=True,
                        trend_aligned=True,
                        momentum_ok=True
                    )
                    setup_score_arr[i] = score
                    engine_setup_arr[i] = "LIQUIDITY_SWEEP_SHORT"
                    if score >= MIN_SETUP_SCORE:
                        engine_signal_arr[i] = -1.0

        # Запись всех признаков в DataFrame
        data['NEAREST_SUPPORT'] = nearest_sup_arr
        data['NEAREST_RESISTANCE'] = nearest_res_arr
        data['DIST_SUP_PCT'] = dist_sup_pct_arr
        data['DIST_RES_PCT'] = dist_res_pct_arr
        data['SR_STRENGTH'] = sr_strength_arr
        data['MARKET_STRUCTURE'] = market_structure_arr
        data['BOS_LONG'] = bos_long_arr
        data['BOS_SHORT'] = bos_short_arr
        data['CHOCH_LONG'] = choch_long_arr
        data['CHOCH_SHORT'] = choch_short_arr
        data['BREAKOUT_STRENGTH'] = breakout_strength_arr
        data['BREAKOUT_VOLUME_RATIO'] = breakout_vol_ratio_arr
        data['IS_BREAKOUT_LONG'] = is_breakout_long_arr
        data['IS_BREAKOUT_SHORT'] = is_breakout_short_arr
        data['IS_RETEST_LONG'] = is_retest_long_arr
        data['IS_RETEST_SHORT'] = is_retest_short_arr
        data['LIQUIDITY_SWEEP_HIGH'] = sweep_high_arr
        data['LIQUIDITY_SWEEP_LOW'] = sweep_low_arr
        data['SETUP_SCORE'] = setup_score_arr
        data['engine_setup'] = engine_setup_arr
        data['engine_signal'] = engine_signal_arr

        return data


def enrich_with_market_structure(df: pd.DataFrame) -> pd.DataFrame:
    """Удобный хелпер для быстрого вызова движка."""
    engine = MarketStructureEngine()
    return engine.analyze(df)
