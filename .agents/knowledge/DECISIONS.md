# Architecture Decisions

## Decision 001
**Date**: 2026-09-04
**Decision**: Hybrid Signal Engine (TA + ML).
**Reason**: Traditional TA generates too many false positives. By using a programmatic `MarketStructureEngine` to generate high-quality structural setups and scoring them, we create a solid baseline. We then use an ML model (XGBoost) strictly as a *filter* (meta-labeling) to reject low-probability setups based on historical feature correlations.
**Constraint**: Do not remove the two-step process. The TA engine must generate the features, and the ML engine must filter them.

## Decision 002
**Date**: 2026-09-04
**Decision**: Structure-Based Risk Management.
**Reason**: Fixed percentage stop-losses get hunted and don't respect market context. The `StructureRiskEngine` places protective stops beyond invalidation points (swing highs/lows, broken zones) with an ATR buffer. Position sizing is dynamically adjusted so that a hit to the structural SL results in a fixed USD risk.
**Constraint**: Do not revert to fixed % SL/TP unless explicitly requested. Always pass `setup_type` and `engine_context` to the executor.

## Decision 003
**Date**: 2026-09-04
**Decision**: Zero Lookahead Bias in Market Structure.
**Reason**: To ensure that ML training data matches live execution exactly, `market_structure.py` must only use data available up to candle `i` to evaluate candle `i`. Swing detection waits for `k` bars to confirm.
**Constraint**: Never modify `market_structure.py` to use future data (e.g., `shift(-1)`) for live signal generation.
