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
    SCORE_ADX_MIN,
    RANGE_MAX_EXPANSION_ATR,
    RANGE_MIN_TOUCHES,
    PULLBACK_MAX_DEPTH_ATR,
    logger
)

class SRZone:
    """
    Зона поддержки или сопротивления с динамической шириной по ATR,
    кластеризацией и расчетом реальной силы (SR_STRENGTH: 0-100).
    """
    def __init__(self, price: float, atr: float, zone_type: str, candle_idx: int, volume: float = 1.0):
        self.center: float = price
        self.zone_type: str = zone_type  # 'SUPPORT' or 'RESISTANCE'
        self.atr: float = max(atr, price * 0.001)
        half_width = (self.atr * SR_ZONE_ATR_MULTIPLIER) / 2.0
        self.high: float = price + half_width
        self.low: float = price - half_width
        self.touch_count: int = 1
        self.first_idx: int = candle_idx
        self.last_idx: int = candle_idx
        self.touch_volumes: List[float] = [volume]
        self.max_bounce_atr: float = 0.0
        self.strength: float = 30.0

    def update_touch(self, price: float, atr: float, candle_idx: int, volume: float = 1.0):
        """Объединение близкого свинга в зону и пересчет ее характеристик."""
        self.touch_count += 1
        self.last_idx = candle_idx
        self.touch_volumes.append(volume)
        self.atr = max(atr, price * 0.001)
        # Сдвигаем центр к средневзвешенному
        self.center = (self.center * (self.touch_count - 1) + price) / self.touch_count
        half_width = (self.atr * SR_ZONE_ATR_MULTIPLIER) / 2.0
        self.high = self.center + half_width
        self.low = self.center - half_width

    def update_bounce(self, bounce_distance_atr: float):
        """Регистрация величины отскока цены от зоны."""
        if bounce_distance_atr > self.max_bounce_atr:
            self.max_bounce_atr = bounce_distance_atr

    def calculate_strength(self, current_candle_idx: int) -> float:
        """
        Реальный расчет силы уровня (P1. 7):
        - Количество подтвержденных касаний
        - Объем на касаниях
        - Сила отскока цены (bounce magnitude)
        - Свежесть (recency)
        """
        base = 25.0
        # 1. Бонус за касания (до 35 баллов)
        touch_pts = min(35.0, (self.touch_count - 1) * 12.0)
        
        # 2. Бонус за средний объем на касаниях (до 15 баллов)
        avg_vol = np.mean(self.touch_volumes) if self.touch_volumes else 1.0
        vol_pts = 15.0 if avg_vol >= 1.25 else (8.0 if avg_vol >= 1.0 else 0.0)
        
        # 3. Бонус за силу реакции/отскока цены (до 15 баллов)
        bounce_pts = min(15.0, self.max_bounce_atr * 7.5)
        
        # 4. Бонус за свежесть уровня (до 10 баллов)
        bars_ago = current_candle_idx - self.last_idx
        recency_pts = 10.0 if bars_ago <= 30 else (5.0 if bars_ago <= 80 else 0.0)
        
        self.strength = min(100.0, base + touch_pts + vol_pts + bounce_pts + recency_pts)
        return self.strength


class MarketStructureEngine:
    """
    Полнофункциональный движок рыночной структуры и Price Action.
    Работает строго без заглядывания в будущее (Zero Lookahead Bias).
    Единый движок для Live и Training.
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
        direction: str,
        has_breakout: bool,
        has_retest: bool,
        has_rejection: bool,
        vol_ratio: float,
        structure_aligned: bool,
        ema_fast: float,
        ema_slow: float,
        close: float,
        vwap: float,
        rsi: float,
        price_roc: float,
        adx: float,
        log_diagnostics: bool = False
    ) -> float:
        """
        Реальный расчет силы сетапа (P0. 1):
        Никаких заглушек True! Оценивает фактические рыночные индикаторы свечи.
        """
        b_pts = SCORE_WEIGHT_BREAKOUT if has_breakout else 0.0
        r_pts = SCORE_WEIGHT_RETEST if has_retest else 0.0
        rej_pts = SCORE_WEIGHT_REJECTION if has_rejection else 0.0
        
        # Объем
        if vol_ratio >= 1.25:
            v_pts = SCORE_WEIGHT_VOLUME
        elif vol_ratio >= 1.0:
            v_pts = SCORE_WEIGHT_VOLUME * 0.6
        else:
            v_pts = 0.0
            
        # Структура
        s_pts = SCORE_WEIGHT_STRUCTURE if structure_aligned else 0.0
        
        # Реальный тренд
        if direction == 'LONG':
            trend_cond = (ema_fast >= ema_slow) and (close >= vwap) and (adx >= SCORE_ADX_MIN)
        else:
            trend_cond = (ema_fast <= ema_slow) and (close <= vwap) and (adx >= SCORE_ADX_MIN)
        t_pts = SCORE_WEIGHT_TREND if trend_cond else 0.0
        
        # Реальный моментум
        if direction == 'LONG':
            mom_cond = (48.0 <= rsi <= 70.0) or (price_roc > 0.0)
        else:
            mom_cond = (30.0 <= rsi <= 52.0) or (price_roc < 0.0)
        m_pts = SCORE_WEIGHT_MOMENTUM if mom_cond else 0.0

        total = min(100.0, b_pts + r_pts + rej_pts + v_pts + s_pts + t_pts + m_pts)

        if log_diagnostics:
            self.logger.debug(
                f"SETUP SCORE [{direction}]: breakout={b_pts:.0f}, retest={r_pts:.0f}, "
                f"rejection={rej_pts:.0f}, volume={v_pts:.0f}, structure={s_pts:.0f}, "
                f"trend={t_pts:.0f}, momentum={m_pts:.0f}, TOTAL={total:.0f}"
            )

        return total

    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Главная точка входа движка: анализирует рынок и возвращает датафрейм
        с уровнями, зонами, структурой, сетапами и машиной состояний.
        """
        if df is None or df.empty:
            return df

        data = df.copy()

        # 1. Безопасный расчет ATR если он не передан
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

        # Базовые индикаторы для Setup Score (если еще не в data)
        c_series = data['close']
        ema_f_arr = data['EMA_FAST'].values if 'EMA_FAST' in data.columns else c_series.ewm(span=21).mean().values
        ema_s_arr = data['EMA_SLOW'].values if 'EMA_SLOW' in data.columns else c_series.ewm(span=50).mean().values
        vwap_arr = data['VWAP'].values if 'VWAP' in data.columns else c_series.values
        rsi_arr = data['RSI'].values if 'RSI' in data.columns else np.full(len(data), 50.0)
        roc_arr = data['PRICE_ROC'].values if 'PRICE_ROC' in data.columns else c_series.pct_change(14).fillna(0.0).values
        adx_arr = data['ADX'].values if 'ADX' in data.columns else np.full(len(data), 25.0)

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

        # Активные зоны и свинги
        active_support_zones: List[SRZone] = []
        active_resistance_zones: List[SRZone] = []
        confirmed_swing_highs: List[Tuple[int, float]] = []  # (candle_idx, price)
        confirmed_swing_lows: List[Tuple[int, float]] = []   # (candle_idx, price)

        # P0. 2: Структурные protected экстремумы
        protected_high: Optional[float] = None
        protected_low: Optional[float] = None
        current_structure: str = "RANGE"  # "BULLISH", "BEARISH", "RANGE"

        # P0. 3: Множественная машина состояний Breakout-Retest
        active_breakout_setups: List[Dict] = []
        consumed_setup_ids = set()

        k = self.swing_k

        for i in range(n):
            curr_c = closes[i]
            curr_h = highs[i]
            curr_l = lows[i]
            curr_atr = atrs[i] if atrs[i] > 0 else curr_c * 0.01
            curr_vol_ratio = vol_ratio_arr[i]

            # --- A. ДЕТЕКЦИЯ СВИНГОВ (ZERO LOOKAHEAD) ---
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
                    confirmed_swing_highs.append((cand_idx, cand_h))
                    # Кластеризация зон сопротивления
                    merged = False
                    merge_tol = cand_atr * SR_MERGE_TOLERANCE_ATR
                    for zone in active_resistance_zones:
                        if abs(zone.center - cand_h) <= merge_tol:
                            zone.update_touch(cand_h, cand_atr, cand_idx, volume=vol_ratio_arr[cand_idx])
                            merged = True
                            break
                    if not merged:
                        active_resistance_zones.append(
                            SRZone(cand_h, cand_atr, 'RESISTANCE', cand_idx, volume=vol_ratio_arr[cand_idx])
                        )

                # Проверка Swing Low: строго ниже всех соседей в окне [-k, +k]
                is_sl = True
                for offset in range(-k, k + 1):
                    if offset != 0 and lows[cand_idx + offset] <= cand_l:
                        is_sl = False
                        break
                if is_sl:
                    confirmed_swing_lows.append((cand_idx, cand_l))
                    # Кластеризация зон поддержки
                    merged = False
                    merge_tol = cand_atr * SR_MERGE_TOLERANCE_ATR
                    for zone in active_support_zones:
                        if abs(zone.center - cand_l) <= merge_tol:
                            zone.update_touch(cand_l, cand_atr, cand_idx, volume=vol_ratio_arr[cand_idx])
                            merged = True
                            break
                    if not merged:
                        active_support_zones.append(
                            SRZone(cand_l, cand_atr, 'SUPPORT', cand_idx, volume=vol_ratio_arr[cand_idx])
                        )

                # Ограничиваем списки зон
                if len(active_resistance_zones) > 25:
                    active_resistance_zones.pop(0)
                if len(active_support_zones) > 25:
                    active_support_zones.pop(0)
                if len(confirmed_swing_highs) > 30:
                    confirmed_swing_highs.pop(0)
                if len(confirmed_swing_lows) > 30:
                    confirmed_swing_lows.pop(0)

                # Обновление структуры при подтверждении нового свинга
                if len(confirmed_swing_highs) >= 2 and len(confirmed_swing_lows) >= 2:
                    sh1, sh2 = confirmed_swing_highs[-1][1], confirmed_swing_highs[-2][1]
                    sl1, sl2 = confirmed_swing_lows[-1][1], confirmed_swing_lows[-2][1]
                    if sh1 > sh2 and sl1 > sl2:
                        current_structure = "BULLISH"
                        protected_high = sh1
                        protected_low = sl1
                    elif sh1 < sh2 and sl1 < sl2:
                        current_structure = "BEARISH"
                        protected_high = sh1
                        protected_low = sl1
                    else:
                        current_structure = "RANGE"
                        protected_high = max(sh1, sh2)
                        protected_low = min(sl1, sl2)

            # Обновление реакций зон (bounce magnitude)
            for z in active_support_zones:
                if curr_c > z.high:
                    z.update_bounce((curr_c - z.high) / curr_atr)
            for z in active_resistance_zones:
                if curr_c < z.low:
                    z.update_bounce((z.low - curr_c) / curr_atr)

            # --- B. ПОИСК АКТИВНЫХ ЗОН S/R И ИХ СИЛЫ ---
            valid_sups = [z for z in active_support_zones if z.high < curr_c]
            if valid_sups:
                best_sup_zone = max(valid_sups, key=lambda z: z.high)
                nearest_sup = best_sup_zone.high
                sup_dist = (curr_c - nearest_sup) / curr_c
                sup_strength = best_sup_zone.calculate_strength(i)
            else:
                nearest_sup = curr_c * 0.95
                sup_dist = 0.05
                sup_strength = 20.0

            valid_res = [z for z in active_resistance_zones if z.low > curr_c]
            if valid_res:
                best_res_zone = min(valid_res, key=lambda z: z.low)
                nearest_res = best_res_zone.low
                res_dist = (nearest_res - curr_c) / curr_c
                res_strength = best_res_zone.calculate_strength(i)
            else:
                nearest_res = curr_c * 1.05
                res_dist = 0.05
                res_strength = 20.0

            nearest_sup_arr[i] = nearest_sup
            nearest_res_arr[i] = nearest_res
            dist_sup_pct_arr[i] = max(0.0, sup_dist)
            dist_res_pct_arr[i] = max(0.0, res_dist)
            sr_strength_arr[i] = max(sup_strength, res_strength)

            # Численное значение структуры
            struct_val = 1.0 if current_structure == "BULLISH" else (-1.0 if current_structure == "BEARISH" else 0.0)
            market_structure_arr[i] = struct_val

            # --- C. ТОЧЕЧНЫЕ СОБЫТИЯ BOS И CHOCH (P0. 2) ---
            if i >= 1 and protected_high is not None and protected_low is not None:
                # 1. BOS LONG: свеча закрылась выше protected_high при бычьей структуре
                if closes[i-1] <= protected_high and curr_c > protected_high and current_structure == "BULLISH":
                    bos_long_arr[i] = 1.0
                    protected_high = curr_h  # Обновляем protected_high, чтобы событие было строго точечным

                # 2. BOS SHORT: свеча закрылась ниже protected_low при медвежьей структуре
                elif closes[i-1] >= protected_low and curr_c < protected_low and current_structure == "BEARISH":
                    bos_short_arr[i] = 1.0
                    protected_low = curr_l

                # 3. CHOCH LONG: закрытие выше protected_high при медвежьей структуре (слом структуры в лонг)
                elif closes[i-1] <= protected_high and curr_c > protected_high and current_structure == "BEARISH":
                    choch_long_arr[i] = 1.0
                    current_structure = "BULLISH"
                    protected_high = curr_h

                # 4. CHOCH SHORT: закрытие ниже protected_low при бычьей структуре (слом структуры в шорт)
                elif closes[i-1] >= protected_low and curr_c < protected_low and current_structure == "BULLISH":
                    choch_short_arr[i] = 1.0
                    current_structure = "BEARISH"
                    protected_low = curr_l

            # --- D. СТРОГИЙ LIQUIDITY SWEEP (P1. 8) ---
            # LONG Sweep: цена прокалывает поддержку / protected_low тенью, но закрывается обратно внутри
            ref_low = protected_low if protected_low is not None else nearest_sup
            if curr_l < (ref_low - curr_atr * 0.05) and curr_c >= ref_low:
                sweep_low_arr[i] = 1.0

            # SHORT Sweep: цена прокалывает сопротивление / protected_high тенью, но закрывается обратно внутри
            ref_high = protected_high if protected_high is not None else nearest_res
            if curr_h > (ref_high + curr_atr * 0.05) and curr_c <= ref_high:
                sweep_high_arr[i] = 1.0

            # --- E. ДЕТЕКЦИЯ ПРОБОЕВ (BREAKOUT) ---
            breakout_buf = max(curr_atr * BREAKOUT_ATR_MULTIPLIER, curr_c * MIN_BREAKOUT_PCT)

            # Пробой сопротивления (LONG)
            for z in active_resistance_zones:
                if i >= 1 and closes[i-1] <= z.high and curr_c > (z.high + breakout_buf):
                    is_breakout_long_arr[i] = 1.0
                    bo_str = (curr_c - z.high) / curr_atr
                    breakout_strength_arr[i] = bo_str
                    breakout_vol_ratio_arr[i] = curr_vol_ratio
                    setup_id = f"BO_LONG_{z.first_idx}_{z.center:.2f}"
                    if setup_id not in consumed_setup_ids:
                        # P0. 3: Добавляем в список активных сетапов с фиксированным broken_level
                        active_breakout_setups.append({
                            'id': setup_id,
                            'direction': 'LONG',
                            'broken_level': z.center,
                            'zone_low': z.low,
                            'zone_high': z.high,
                            'breakout_idx': i,
                            'breakout_price': curr_c,
                            'breakout_strength': bo_str,
                            'breakout_vol': curr_vol_ratio,
                            'bars_waiting': 0,
                            'state': 'WAITING_RETEST'
                        })
                    break

            # Пробой поддержки (SHORT)
            for z in active_support_zones:
                if i >= 1 and closes[i-1] >= z.low and curr_c < (z.low - breakout_buf):
                    is_breakout_short_arr[i] = 1.0
                    bo_str = (z.low - curr_c) / curr_atr
                    breakout_strength_arr[i] = bo_str
                    breakout_vol_ratio_arr[i] = curr_vol_ratio
                    setup_id = f"BO_SHORT_{z.first_idx}_{z.center:.2f}"
                    if setup_id not in consumed_setup_ids:
                        active_breakout_setups.append({
                            'id': setup_id,
                            'direction': 'SHORT',
                            'broken_level': z.center,
                            'zone_low': z.low,
                            'zone_high': z.high,
                            'breakout_idx': i,
                            'breakout_price': curr_c,
                            'breakout_strength': bo_str,
                            'breakout_vol': curr_vol_ratio,
                            'bars_waiting': 0,
                            'state': 'WAITING_RETEST'
                        })
                    break

            # --- F. МНОЖЕСТВЕННАЯ STATE MACHINE ДЛЯ RETEST & ENTRY (P0. 3 & P0. 4) ---
            retest_tol = curr_atr * RETEST_TOLERANCE_ATR
            surviving_setups = []

            for setup in active_breakout_setups:
                # Пропускаем только что созданный на текущей свече пробой
                if setup['breakout_idx'] == i:
                    surviving_setups.append(setup)
                    continue

                setup['bars_waiting'] += 1
                bars_w = setup['bars_waiting']
                direction = setup['direction']
                z_high = setup['zone_high']
                z_low = setup['zone_low']

                # 1. Проверка таймаута
                if bars_w > self.retest_max_bars:
                    setup['state'] = 'EXPIRED'
                    continue

                # 2. Проверка инвалидации (обратный провал за буфер)
                if direction == 'LONG' and curr_c < (z_low - curr_atr * INVALIDATION_ATR_MULTIPLIER):
                    setup['state'] = 'INVALIDATED'
                    continue
                elif direction == 'SHORT' and curr_c > (z_high + curr_atr * INVALIDATION_ATR_MULTIPLIER):
                    setup['state'] = 'INVALIDATED'
                    continue

                # 3. Проверка взаимодействия с неизменной зоной пробоя
                if direction == 'LONG':
                    touch_zone = (curr_l <= z_high + retest_tol) and (curr_h >= z_low - curr_atr * 0.2)
                    if touch_zone:
                        setup['state'] = 'RETEST_DETECTED'
                        # Подтверждение удержания
                        confirmed = (curr_c >= z_low) and (bull_rej[i] or bull_eng[i] or curr_c > opens[i])
                        if confirmed:
                            setup['state'] = 'ENTRY_READY'
                            is_retest_long_arr[i] = 1.0
                            score = self.calculate_setup_score(
                                direction='LONG',
                                has_breakout=True,
                                has_retest=True,
                                has_rejection=bool(bull_rej[i] or bull_eng[i]),
                                vol_ratio=setup['breakout_vol'],
                                structure_aligned=(current_structure == 'BULLISH'),
                                ema_fast=ema_f_arr[i],
                                ema_slow=ema_s_arr[i],
                                close=curr_c,
                                vwap=vwap_arr[i],
                                rsi=rsi_arr[i],
                                price_roc=roc_arr[i],
                                adx=adx_arr[i]
                            )
                            setup_score_arr[i] = score
                            engine_setup_arr[i] = "BREAKOUT_RETEST"
                            if score >= MIN_SETUP_SCORE:
                                engine_signal_arr[i] = 1.0
                            consumed_setup_ids.add(setup['id'])
                            setup['state'] = 'CONSUMED'
                            continue  # Отработан

                elif direction == 'SHORT':
                    touch_zone = (curr_h >= z_low - retest_tol) and (curr_l <= z_high + curr_atr * 0.2)
                    if touch_zone:
                        setup['state'] = 'RETEST_DETECTED'
                        confirmed = (curr_c <= z_high) and (bear_rej[i] or bear_eng[i] or curr_c < opens[i])
                        if confirmed:
                            setup['state'] = 'ENTRY_READY'
                            is_retest_short_arr[i] = 1.0
                            score = self.calculate_setup_score(
                                direction='SHORT',
                                has_breakout=True,
                                has_retest=True,
                                has_rejection=bool(bear_rej[i] or bear_eng[i]),
                                vol_ratio=setup['breakout_vol'],
                                structure_aligned=(current_structure == 'BEARISH'),
                                ema_fast=ema_f_arr[i],
                                ema_slow=ema_s_arr[i],
                                close=curr_c,
                                vwap=vwap_arr[i],
                                rsi=rsi_arr[i],
                                price_roc=roc_arr[i],
                                adx=adx_arr[i]
                            )
                            setup_score_arr[i] = score
                            engine_setup_arr[i] = "BREAKDOWN_RETEST"
                            if score >= MIN_SETUP_SCORE:
                                engine_signal_arr[i] = -1.0
                            consumed_setup_ids.add(setup['id'])
                            setup['state'] = 'CONSUMED'
                            continue

                surviving_setups.append(setup)

            active_breakout_setups = surviving_setups

            # --- G. ДРУГИЕ СЕТАПЫ (P1. 5, P1. 6, P1. 8) ---
            if engine_signal_arr[i] == 0:
                # 1. НАСТОЯЩИЙ TREND PULLBACK (P1. 5)
                # LONG Pullback
                if current_structure == "BULLISH" and protected_low is not None:
                    # Проверяем, что цена в откате к EMA/VWAP/поддержке, но структура цела
                    pullback_zone = min(ema_f_arr[i], vwap_arr[i])
                    is_at_pullback_level = (curr_l <= pullback_zone + curr_atr * 0.5) and (curr_c >= protected_low)
                    if is_at_pullback_level and (bull_rej[i] or bull_eng[i]):
                        score = self.calculate_setup_score(
                            direction='LONG',
                            has_breakout=False,
                            has_retest=True,
                            has_rejection=True,
                            vol_ratio=curr_vol_ratio,
                            structure_aligned=True,
                            ema_fast=ema_f_arr[i],
                            ema_slow=ema_s_arr[i],
                            close=curr_c,
                            vwap=vwap_arr[i],
                            rsi=rsi_arr[i],
                            price_roc=roc_arr[i],
                            adx=adx_arr[i]
                        )
                        setup_score_arr[i] = score
                        engine_setup_arr[i] = "TREND_PULLBACK"
                        if score >= MIN_SETUP_SCORE:
                            engine_signal_arr[i] = 1.0

                # SHORT Pullback
                elif current_structure == "BEARISH" and protected_high is not None:
                    pullback_zone = max(ema_f_arr[i], vwap_arr[i])
                    is_at_pullback_level = (curr_h >= pullback_zone - curr_atr * 0.5) and (curr_c <= protected_high)
                    if is_at_pullback_level and (bear_rej[i] or bear_eng[i]):
                        score = self.calculate_setup_score(
                            direction='SHORT',
                            has_breakout=False,
                            has_retest=True,
                            has_rejection=True,
                            vol_ratio=curr_vol_ratio,
                            structure_aligned=True,
                            ema_fast=ema_f_arr[i],
                            ema_slow=ema_s_arr[i],
                            close=curr_c,
                            vwap=vwap_arr[i],
                            rsi=rsi_arr[i],
                            price_roc=roc_arr[i],
                            adx=adx_arr[i]
                        )
                        setup_score_arr[i] = score
                        engine_setup_arr[i] = "TREND_PULLBACK_DOWN"
                        if score >= MIN_SETUP_SCORE:
                            engine_signal_arr[i] = -1.0

                # 2. НАСТОЯЩИЙ RANGE DETECTION & BOUNCE (P1. 6)
                if engine_signal_arr[i] == 0 and current_structure == "RANGE":
                    if len(confirmed_swing_highs) >= RANGE_MIN_TOUCHES and len(confirmed_swing_lows) >= RANGE_MIN_TOUCHES:
                        range_top = np.mean([p for _, p in confirmed_swing_highs[-RANGE_MIN_TOUCHES:]])
                        range_bottom = np.mean([p for _, p in confirmed_swing_lows[-RANGE_MIN_TOUCHES:]])
                        range_height = range_top - range_bottom
                        
                        if range_height <= curr_atr * RANGE_MAX_EXPANSION_ATR:
                            # Нижняя граница -> Отскок в лонг
                            if (curr_l <= range_bottom + curr_atr * 0.4) and (curr_c >= range_bottom) and (bull_rej[i] or bull_eng[i]):
                                score = self.calculate_setup_score(
                                    direction='LONG',
                                    has_breakout=False,
                                    has_retest=True,
                                    has_rejection=True,
                                    vol_ratio=curr_vol_ratio,
                                    structure_aligned=True,
                                    ema_fast=ema_f_arr[i],
                                    ema_slow=ema_s_arr[i],
                                    close=curr_c,
                                    vwap=vwap_arr[i],
                                    rsi=rsi_arr[i],
                                    price_roc=roc_arr[i],
                                    adx=adx_arr[i]
                                )
                                setup_score_arr[i] = score
                                engine_setup_arr[i] = "RANGE_BOUNCE"
                                if score >= MIN_SETUP_SCORE:
                                    engine_signal_arr[i] = 1.0

                            # Верхняя граница -> Отбой в шорт
                            elif (curr_h >= range_top - curr_atr * 0.4) and (curr_c <= range_top) and (bear_rej[i] or bear_eng[i]):
                                score = self.calculate_setup_score(
                                    direction='SHORT',
                                    has_breakout=False,
                                    has_retest=True,
                                    has_rejection=True,
                                    vol_ratio=curr_vol_ratio,
                                    structure_aligned=True,
                                    ema_fast=ema_f_arr[i],
                                    ema_slow=ema_s_arr[i],
                                    close=curr_c,
                                    vwap=vwap_arr[i],
                                    rsi=rsi_arr[i],
                                    price_roc=roc_arr[i],
                                    adx=adx_arr[i]
                                )
                                setup_score_arr[i] = score
                                engine_setup_arr[i] = "RANGE_REJECTION"
                                if score >= MIN_SETUP_SCORE:
                                    engine_signal_arr[i] = -1.0

                # 3. LIQUIDITY SWEEP СТРОГИЙ (P1. 8)
                if engine_signal_arr[i] == 0:
                    if sweep_low_arr[i] == 1.0 and (bull_rej[i] or bull_eng[i]):
                        score = self.calculate_setup_score(
                            direction='LONG',
                            has_breakout=False,
                            has_retest=True,
                            has_rejection=True,
                            vol_ratio=curr_vol_ratio,
                            structure_aligned=(current_structure != 'BEARISH'),
                            ema_fast=ema_f_arr[i],
                            ema_slow=ema_s_arr[i],
                            close=curr_c,
                            vwap=vwap_arr[i],
                            rsi=rsi_arr[i],
                            price_roc=roc_arr[i],
                            adx=adx_arr[i]
                        )
                        setup_score_arr[i] = score
                        engine_setup_arr[i] = "LIQUIDITY_SWEEP_LONG"
                        if score >= MIN_SETUP_SCORE:
                            engine_signal_arr[i] = 1.0

                    elif sweep_high_arr[i] == 1.0 and (bear_rej[i] or bear_eng[i]):
                        score = self.calculate_setup_score(
                            direction='SHORT',
                            has_breakout=False,
                            has_retest=True,
                            has_rejection=True,
                            vol_ratio=curr_vol_ratio,
                            structure_aligned=(current_structure != 'BULLISH'),
                            ema_fast=ema_f_arr[i],
                            ema_slow=ema_s_arr[i],
                            close=curr_c,
                            vwap=vwap_arr[i],
                            rsi=rsi_arr[i],
                            price_roc=roc_arr[i],
                            adx=adx_arr[i]
                        )
                        setup_score_arr[i] = score
                        engine_setup_arr[i] = "LIQUIDITY_SWEEP_SHORT"
                        if score >= MIN_SETUP_SCORE:
                            engine_signal_arr[i] = -1.0

                # 4. SUPPORT BOUNCE / RESISTANCE REJECTION
                if engine_signal_arr[i] == 0:
                    if dist_sup_pct_arr[i] <= (curr_atr * 0.8 / curr_c) and (bull_rej[i] or bull_eng[i]):
                        score = self.calculate_setup_score(
                            direction='LONG',
                            has_breakout=False,
                            has_retest=True,
                            has_rejection=True,
                            vol_ratio=curr_vol_ratio,
                            structure_aligned=(current_structure != 'BEARISH'),
                            ema_fast=ema_f_arr[i],
                            ema_slow=ema_s_arr[i],
                            close=curr_c,
                            vwap=vwap_arr[i],
                            rsi=rsi_arr[i],
                            price_roc=roc_arr[i],
                            adx=adx_arr[i]
                        )
                        setup_score_arr[i] = score
                        engine_setup_arr[i] = "SUPPORT_BOUNCE"
                        if score >= MIN_SETUP_SCORE:
                            engine_signal_arr[i] = 1.0

                    elif dist_res_pct_arr[i] <= (curr_atr * 0.8 / curr_c) and (bear_rej[i] or bear_eng[i]):
                        score = self.calculate_setup_score(
                            direction='SHORT',
                            has_breakout=False,
                            has_retest=True,
                            has_rejection=True,
                            vol_ratio=curr_vol_ratio,
                            structure_aligned=(current_structure != 'BULLISH'),
                            ema_fast=ema_f_arr[i],
                            ema_slow=ema_s_arr[i],
                            close=curr_c,
                            vwap=vwap_arr[i],
                            rsi=rsi_arr[i],
                            price_roc=roc_arr[i],
                            adx=adx_arr[i]
                        )
                        setup_score_arr[i] = score
                        engine_setup_arr[i] = "RESISTANCE_REJECTION"
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
    """Удобный хелпер для вызова движка."""
    engine = MarketStructureEngine()
    return engine.analyze(df)
