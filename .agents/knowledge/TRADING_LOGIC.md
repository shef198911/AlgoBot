# Current Trading Logic

## Market Data
- Fetches OHLCV data using Binance API. 
- Operates on specific symbols configured in `config.py`.
- Supports NORMAL (15m timeframe, 1h trend) and SCALPING (1m timeframe, 15m trend) modes.

## Indicators & Market Structure
- Zero-lookahead bias `MarketStructureEngine` calculates Swing Highs/Lows, Support/Resistance zones, ATR, RSI, VWAP, EMA Fast/Slow, ADX, Price ROC.
- Detects structural shifts like Break of Structure (BOS), Change of Character (CHOCH), Liquidity Sweeps, and Breakout/Retest states.

## Signal Generation (TA Engine)
- Generates setups: `BREAKOUT_RETEST`, `BREAKDOWN_RETEST`, `TREND_PULLBACK`, `RANGE_BOUNCE`, `RANGE_REJECTION`, `LIQUIDITY_SWEEP_LONG`, `LIQUIDITY_SWEEP_SHORT`.
- Calculates a `setup_score` (max 100) based on breakout strength, retest validity, candle rejection (pinbars, engulfing), volume, structure alignment, trend, and momentum.
- A raw signal is generated if `setup_score >= MIN_SETUP_SCORE` (default 55).

## Confirmation (ML Filter)
- The raw signal and its features are passed to `MLFilter`.
- An XGBoost classifier evaluates the probability of success.
- The trade is APPROVED only if the AI confidence is >= `ML_PROBABILITY_THRESHOLD` (default 0.55).

## Entry
- Executed by `TraderExecutor`. 
- Calculates position size dynamically based on the risk distance (Stop Loss distance) and `TRADE_SIZE_USDT` (if structure risk is enabled).
- Opens MARKET orders.

## Position Management & Risk
- Managed by `StructureRiskEngine`.
- **Stop Loss**: Placed dynamically based on structural invalidation levels (e.g., just below the nearest support or swing low for longs), with an ATR buffer. Protected by `MIN_SL_ATR` and `MAX_SL_ATR`.
- **Take Profit**: Targeted at nearest structural resistance/support levels, or using a fallback Risk/Reward ratio (`MIN_RR = 1.5`).
- **Trailing Stop**: If `USE_TRAILING` is true, trailing stop activates after `TRAILING_ACTIVATION_PCT` profit is reached, trailing by `TRAILING_DISTANCE_PCT`.
- Emergency closures are triggered if SL/TP orders fail to place.

## Exit
- Can exit via Stop Loss hit, Take Profit hit, or Trailing Stop market closure.
- On exit, PnL is calculated from Binance `fetch_my_trades` and recorded in analytics.
