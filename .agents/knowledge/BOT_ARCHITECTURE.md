# Project Architecture

## Purpose
AlgoBot is a hybrid AI-driven cryptocurrency trading bot. It combines rule-based Price Action and Market Structure analysis (Technical Analysis) with Machine Learning (XGBoost meta-labeling) to filter setups and execute trades on Binance.

## Main Components
- **main.py**: The entry point and main event loop coordinating data fetching, analysis, filtering, and execution.
- **config.py**: Global configuration, trading modes, risk parameters, and feature column definitions.
- **data_fetcher.py**: Handles fetching historical klines and global trend data from the exchange.
- **market_structure.py**: The core Price Action engine. Performs zero lookahead bias detection of swing highs/lows, support/resistance zones, BOS, CHOCH, breakouts, and liquidity sweeps.
- **strategy_ta.py**: Wrapper around the market structure engine that generates feature sets and raw trade signals based on setup scores.
- **ml_filter.py**: The Machine Learning meta-labeling component. Evaluates the TA signals using pre-trained XGBoost models (`.pkl` and `.json`) to approve or reject trades based on a probability threshold.
- **risk_manager.py**: `StructureRiskEngine` that calculates structural stop losses and take profits based on the market context (swing levels, broken levels, ATR) rather than fixed percentages.
- **executor.py**: `TraderExecutor` handles actual exchange execution, position state management, trailing stops, and emergency closure logic.
- **telegram_notifier.py**: Sends live trade notifications and updates to Telegram.

## External Services
- **Binance Exchange API** (Testnet / Mainnet)
- **Telegram Bot API** (Notifications)

## Data Storage
- Local `live_state.json` for tracking active positions and order IDs across restarts.
- `trade_history.txt` and `bot.log` for logs.
- `bot_data.sqlite` / `analytics_data.json` for trade analytics.

## Important Architectural Constraints
- **Zero Lookahead Bias**: The `market_structure.py` must never use future data to detect swings or levels.
- **Two-Step Verification**: Trades must pass both the TA engine (`setup_score >= MIN_SETUP_SCORE`) and the ML filter (`probability >= ML_PROBABILITY_THRESHOLD`).
- **State Recovery**: The executor must be able to recover position state from exchange APIs and `live_state.json` if it restarts.
