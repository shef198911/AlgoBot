# Trading Logic Rules

Always respect the trading logic and pipeline described in:
@../knowledge/TRADING_LOGIC.md

When modifying trading logic:
- Preserve the TA -> ML Filter pipeline.
- Maintain Zero Lookahead Bias in `market_structure.py`.
- Do not simplify risk management. Use `StructureRiskEngine` over fixed percentages unless told otherwise.
- Account for execution edge cases (API failures, partial fills, trailing stop triggers).
