import pandas as pd
import numpy as np
from ta.trend import EMAIndicator, ADXIndicator
from config import TRADING_MODE, TREND_TIMEFRAME

def evaluate_trend(fast, slow, close, adx_val):
    if (pd.isna(fast) or pd.isna(slow) or pd.isna(close) or pd.isna(adx_val) or 
            slow == 0 or fast == 0 or close == 0):
        return 'UNKNOWN'
        
    ema_dist = (fast - slow) / slow
    
    if fast > slow and close > fast:
        if adx_val > 25 and ema_dist > 0.002:
            return 'STRONG_BULL'
        else:
            return 'BULL'
    elif fast < slow and close < fast:
        if adx_val > 25 and ema_dist < -0.002:
            return 'STRONG_BEAR'
        else:
            return 'BEAR'
    else:
        return 'RANGE'

def _get_htf_dataframe(fetcher, symbol, limit=500):
    tf = TREND_TIMEFRAME
    if TRADING_MODE == 'SCALPING':
        fast_window, slow_window = 21, 50
    else:
        fast_window, slow_window = 9, 21
        
    df_htf = fetcher.get_historical_klines(symbol, tf, limit=limit)
    if df_htf is None or df_htf.empty or len(df_htf) < slow_window + 14:
        return None
        
    df_htf['EMA_FAST'] = EMAIndicator(close=df_htf['close'], window=fast_window).ema_indicator()
    df_htf['EMA_SLOW'] = EMAIndicator(close=df_htf['close'], window=slow_window).ema_indicator()
    
    try:
        adx = ADXIndicator(high=df_htf['high'], low=df_htf['low'], close=df_htf['close'], window=14)
        df_htf['ADX'] = adx.adx()
    except:
        df_htf['ADX'] = np.nan
        
    return df_htf

def get_global_trend(fetcher, symbol):
    # Live uses same 500-bar limit to ensure EMA and ADX indicator convergence parity with training
    df_htf = _get_htf_dataframe(fetcher, symbol, limit=500)
    if df_htf is None or df_htf.empty:
        return "UNKNOWN"
        
    last_row = df_htf.iloc[-1]
    fast = last_row.get('EMA_FAST', np.nan)
    slow = last_row.get('EMA_SLOW', np.nan)
    close = last_row.get('close', np.nan)
    adx_val = last_row.get('ADX', np.nan)
    
    return evaluate_trend(fast, slow, close, adx_val)

def add_global_trend(df, fetcher, symbol):
    if df is None or df.empty:
        return df

    tf = TREND_TIMEFRAME
    df_htf = _get_htf_dataframe(fetcher, symbol, limit=1500)
    
    if df_htf is None or df_htf.empty:
        df['HTF_TREND'] = 'UNKNOWN'
        return df
        
    def get_trend_str(row):
        fast = row.get('EMA_FAST', 0)
        slow = row.get('EMA_SLOW', 0)
        close = row.get('close', 0)
        adx_val = row.get('ADX', 0)
        return evaluate_trend(fast, slow, close, adx_val)

    df_htf['HTF_TREND'] = df_htf.apply(get_trend_str, axis=1)
    
    # Map back to lower timeframe
    df_htf['close_time'] = df_htf['timestamp'] + pd.to_timedelta(tf)
    
    df_htf = df_htf[['close_time', 'HTF_TREND']].dropna().sort_values('close_time')
    if df_htf.empty:
        df['HTF_TREND'] = 'UNKNOWN'
        return df

    if 'HTF_TREND' in df.columns:
        df = df.drop(columns=['HTF_TREND'])

    df = df.sort_values('timestamp')
    
    df = pd.merge_asof(df, df_htf, left_on='timestamp', right_on='close_time', direction='backward')
    if 'HTF_TREND' in df.columns:
        df['HTF_TREND'] = df['HTF_TREND'].fillna('UNKNOWN')
    else:
        df['HTF_TREND'] = 'UNKNOWN'
    
    return df


