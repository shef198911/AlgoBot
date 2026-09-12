import numpy as np
import pandas as pd

from ta.trend import ADXIndicator
from ta.volatility import AverageTrueRange

from config import (
    logger,
    DONCHIAN_PERIOD,
    ADX_PERIOD,
    ADX_MIN,
    DI_SPREAD_MIN,
    VOLUME_RATIO_MIN,
    BREAKOUT_MAX_ATR,
    BREAKOUT_MIN_ATR,
    OBV_SLOPE_LOOKBACK,
)


class StrategyV2:
    """
    Strategy V2:
    Donchian Breakout + ADX/DI + Volume + OBV + ATR.
    """

    def __init__(self):
        self.logger = logger.getChild("StrategyV2")

    @staticmethod
    def _calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        direction = np.sign(close.diff()).fillna(0.0)
        return (direction * volume).cumsum()

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return None

        data = df.copy()

        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(data.columns):
            missing = required - set(data.columns)
            self.logger.error(f"Не хватает колонок OHLCV: {missing}")
            return None

        try:
            atr = AverageTrueRange(
                high=data["high"],
                low=data["low"],
                close=data["close"],
                window=14
            )
            data["ATRr"] = atr.average_true_range()

            data["DONCHIAN_HIGH"] = (
                data["high"]
                .rolling(DONCHIAN_PERIOD)
                .max()
                .shift(1)
            )

            data["DONCHIAN_LOW"] = (
                data["low"]
                .rolling(DONCHIAN_PERIOD)
                .min()
                .shift(1)
            )

            data["DONCHIAN_MID"] = (
                data["DONCHIAN_HIGH"] + data["DONCHIAN_LOW"]
            ) / 2.0

            data["CHANNEL_WIDTH_ATR"] = (
                (data["DONCHIAN_HIGH"] - data["DONCHIAN_LOW"])
                / data["ATRr"].replace(0, np.nan)
            )

            adx = ADXIndicator(
                high=data["high"],
                low=data["low"],
                close=data["close"],
                window=ADX_PERIOD
            )

            data["ADX"] = adx.adx()
            data["DI_PLUS"] = adx.adx_pos()
            data["DI_MINUS"] = adx.adx_neg()

            data["DI_SPREAD"] = data["DI_PLUS"] - data["DI_MINUS"]

            volume_mean = (
                data["volume"]
                .rolling(20)
                .mean()
                .replace(0, np.nan)
            )

            data["VOL_RATIO"] = (
                data["volume"] / volume_mean
            ).replace([np.inf, -np.inf], np.nan)

            data["OBV"] = self._calculate_obv(
                data["close"],
                data["volume"]
            )

            data["OBV_SLOPE"] = (
                data["OBV"] - data["OBV"].shift(OBV_SLOPE_LOOKBACK)
            )

            data["BREAKOUT_ATR_LONG"] = (
                (data["close"] - data["DONCHIAN_HIGH"])
                / data["ATRr"].replace(0, np.nan)
            )

            data["BREAKOUT_ATR_SHORT"] = (
                (data["DONCHIAN_LOW"] - data["close"])
                / data["ATRr"].replace(0, np.nan)
            )

            data["CANDLE_RANGE_ATR"] = (
                (data["high"] - data["low"])
                / data["ATRr"].replace(0, np.nan)
            )

            data.replace(
                [np.inf, -np.inf],
                np.nan,
                inplace=True
            )

            data.dropna(inplace=True)

            if data.empty:
                return None

            return data

        except Exception as exc:
            self.logger.error(
                f"Ошибка Strategy V2 при расчёте индикаторов: {exc}"
            )
            return None

    def _long_signal(self, row, previous_row) -> bool:
        breakout = (
            row["close"] > row["DONCHIAN_HIGH"]
            and previous_row["close"] <= previous_row["DONCHIAN_HIGH"]
        )

        trend_strength = row["ADX"] >= ADX_MIN
        direction = row["DI_PLUS"] > (
            row["DI_MINUS"] + DI_SPREAD_MIN
        )

        volume_ok = row["VOL_RATIO"] >= VOLUME_RATIO_MIN

        breakout_size_ok = (
            BREAKOUT_MIN_ATR
            <= row["BREAKOUT_ATR_LONG"]
            <= BREAKOUT_MAX_ATR
        )

        channel_ok = row["CHANNEL_WIDTH_ATR"] >= 1.0
        obv_ok = row["OBV_SLOPE"] > 0
        candle_not_extreme = row["CANDLE_RANGE_ATR"] <= 2.5

        return all([
            breakout,
            trend_strength,
            direction,
            volume_ok,
            breakout_size_ok,
            channel_ok,
            obv_ok,
            candle_not_extreme,
        ])

    def _short_signal(self, row, previous_row) -> bool:
        breakout = (
            row["close"] < row["DONCHIAN_LOW"]
            and previous_row["close"] >= previous_row["DONCHIAN_LOW"]
        )

        trend_strength = row["ADX"] >= ADX_MIN
        direction = row["DI_MINUS"] > (
            row["DI_PLUS"] + DI_SPREAD_MIN
        )

        volume_ok = row["VOL_RATIO"] >= VOLUME_RATIO_MIN

        breakout_size_ok = (
            BREAKOUT_MIN_ATR
            <= row["BREAKOUT_ATR_SHORT"]
            <= BREAKOUT_MAX_ATR
        )

        channel_ok = row["CHANNEL_WIDTH_ATR"] >= 1.0
        obv_ok = row["OBV_SLOPE"] < 0
        candle_not_extreme = row["CANDLE_RANGE_ATR"] <= 2.5

        return all([
            breakout,
            trend_strength,
            direction,
            volume_ok,
            breakout_size_ok,
            channel_ok,
            obv_ok,
            candle_not_extreme,
        ])

    def create_signals(
        self,
        df: pd.DataFrame,
        symbol: str = "UNKNOWN",
        is_live: bool = False
    ) -> pd.DataFrame:

        data = df.copy()

        data["ta_signal"] = 0.0
        data["ta_setup"] = "NONE"
        data["engine_setup"] = "NONE"
        data["engine_context"] = None

        for i in range(1, len(data)):
            row = data.iloc[i]
            previous_row = data.iloc[i - 1]

            long_signal = self._long_signal(row, previous_row)
            short_signal = self._short_signal(row, previous_row)

            if long_signal and not short_signal:
                breakout_level = float(row["DONCHIAN_HIGH"])
                atr = float(row["ATRr"])
                entry = float(row["close"])

                data.at[data.index[i], "ta_signal"] = 1.0
                data.at[data.index[i], "ta_setup"] = "DONCHIAN_BREAKOUT_LONG"
                data.at[data.index[i], "engine_setup"] = "DONCHIAN_BREAKOUT_LONG"

                data.at[data.index[i], "engine_context"] = {
                    "breakout_level": breakout_level,
                    "stop_anchor": breakout_level - (0.75 * atr),
                    "preferred_tp": entry + (2.0 * abs(entry - (
                        breakout_level - (0.75 * atr)
                    ))),
                    "atr": atr,
                    "channel_high": float(row["DONCHIAN_HIGH"]),
                    "channel_low": float(row["DONCHIAN_LOW"]),
                    "channel_mid": float(row["DONCHIAN_MID"]),
                }



            elif short_signal and not long_signal:
                breakout_level = float(row["DONCHIAN_LOW"])
                atr = float(row["ATRr"])
                entry = float(row["close"])

                data.at[data.index[i], "ta_signal"] = -1.0
                data.at[data.index[i], "ta_setup"] = "DONCHIAN_BREAKOUT_SHORT"
                data.at[data.index[i], "engine_setup"] = "DONCHIAN_BREAKOUT_SHORT"

                data.at[data.index[i], "engine_context"] = {
                    "breakout_level": breakout_level,
                    "stop_anchor": breakout_level + (0.75 * atr),
                    "preferred_tp": entry - (2.0 * abs(
                        (breakout_level + (0.75 * atr)) - entry
                    )),
                    "atr": atr,
                    "channel_high": float(row["DONCHIAN_HIGH"]),
                    "channel_low": float(row["DONCHIAN_LOW"]),
                    "channel_mid": float(row["DONCHIAN_MID"]),
                }



        data["SETUP_SCORE"] = np.where(data["ta_signal"] != 0, 100.0, 0.0)
        data["HTF_TREND"] = "STRATEGY_V2"

        return data

    def generate_features_and_signals(
        self,
        df,
        htf_trend="STRATEGY_V2",
        symbol="UNKNOWN",
        is_live=False
    ):
        data = self.calculate_indicators(df)
        if data is None or data.empty:
            return None

        data = self.create_signals(data, symbol=symbol, is_live=is_live)

        if is_live and len(data) > 1:
            data = data.iloc[:-1].copy()

        return data
