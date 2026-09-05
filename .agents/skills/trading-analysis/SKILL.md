---
name: trading-analysis
description: Analyzes trading setups, structural levels, and ML filter conditions for AlgoBot. Use when modifying trading strategies or risk management.
---

# Trading Analysis

Use this skill when modifying AlgoBot's trading logic.

## Process
1. Identify if the change affects TA (signal generation), ML (filtering), or Risk (sizing/SL/TP).
2. Trace the variables through `market_structure.py` -> `strategy_ta.py` -> `main.py` -> `executor.py`.
3. Verify that changes to feature generation do not break the XGBoost model's expected inputs (defined in `config.py` `FEATURE_COLUMNS`).
4. Ensure no lookahead bias is introduced in pandas dataframe operations.
5. Consider API latency and state recovery in `executor.py`.
