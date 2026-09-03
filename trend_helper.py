import pandas as pd
from ta.trend import EMAIndicator
from config import TRADING_MODE, TREND_TIMEFRAME, TIMEFRAME

def add_global_trend(df, fetcher, symbol):
    if df is None or df.empty:
        return df

    # Fetch historical HTF data
    tf = TREND_TIMEFRAME
    if TRADING_MODE == "SCALPING":
        fast_window, slow_window = 21, 50
    else:
        fast_window, slow_window = 9, 21
        
    df_htf = fetcher.get_historical_klines(symbol, tf, limit=1500)
    if df_htf is None or df_htf.empty:
        df['global_trend'] = 0
        return df
        
    df_htf['EMA_FAST_HTF'] = EMAIndicator(close=df_htf['close'], window=fast_window).ema_indicator()
    df_htf['EMA_SLOW_HTF'] = EMAIndicator(close=df_htf['close'], window=slow_window).ema_indicator()
    
    # -1 means trend is down, 1 means up
    df_htf['global_trend'] = 0
    df_htf.loc[df_htf['EMA_FAST_HTF'] > df_htf['EMA_SLOW_HTF'], 'global_trend'] = 1
    df_htf.loc[df_htf['EMA_FAST_HTF'] < df_htf['EMA_SLOW_HTF'], 'global_trend'] = -1
    
    # We want to match each 15m candle with the LAST CLOSED 1h candle.
    # To do this without lookahead bias:
    # merge_asof matches on timestamp.
    # df_htf['timestamp'] is the open time of the 1h candle.
    # If a 15m candle opens at 12:15, the last CLOSED 1h candle is the one that OPENED at 11:00.
    # Its close time was 12:00.
    
    df_htf['close_time'] = df_htf['timestamp'] + pd.to_timedelta(tf)
    
    # We map df['timestamp'] to df_htf['close_time'] where close_time <= timestamp
    df_htf = df_htf[['close_time', 'global_trend']].dropna().sort_values('close_time')
    df = df.sort_values('timestamp')
    
    df = pd.merge_asof(df, df_htf, left_on='timestamp', right_on='close_time', direction='backward')
    df['global_trend'] = df['global_trend'].fillna(0)
    
    return df
