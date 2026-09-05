import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split, RandomizedSearchCV, TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, average_precision_score
import os
import joblib
from config import logger, SYMBOLS, TIMEFRAME, MODEL_FILE, STOP_LOSS_PCT, TAKE_PROFIT_PCT, FEATURE_COLUMNS, ML_HORIZON, TRADING_MODE, DATASET_TARGET_BARS
from data_fetcher import DataFetcher
from strategy_ta import TAStrategy
import entry_gate
from risk_manager import StructureRiskEngine

entry_gate.LOG_ENTRY_GATE = False

def train_ai():
    logger.info("=== Запуск продвинутого обучения ИИ V3 (Triple-Barrier + Ensemble + Regression) ===")
    fetcher = DataFetcher(use_testnet=False)
    all_trades = []
    ta_bot = TAStrategy()
    risk_engine = StructureRiskEngine()

    for symbol in SYMBOLS:
        fetch_limit = DATASET_TARGET_BARS  # Конфигурируемый объем выборки (по умолчанию 1500)
        logger.info(f"Сбор данных для {symbol}... (лимит {fetch_limit})")
        df = fetcher.get_historical_klines(symbol, TIMEFRAME, limit=fetch_limit)
        
        if df is None or df.empty:
            continue

        from trend_helper import add_global_trend
        df = add_global_trend(df, fetcher, symbol)
        ta_bot.current_symbol = symbol
        df_analyzed = ta_bot.generate_features_and_signals(df)

        if df_analyzed is None or df_analyzed.empty:
            logger.warning(f"Пропуск {symbol}: недостаточно данных для расчета индикаторов.")
            continue
        
        
        # Filter TA signals by Global Trend (just like in Live)
        tp_pct = TAKE_PROFIT_PCT
        sl_pct = STOP_LOSS_PCT
        
        closes = df_analyzed['close'].values
        highs = df_analyzed['high'].values
        lows = df_analyzed['low'].values
        signals = df_analyzed['ta_signal'].values
        
        is_success = np.zeros(len(df_analyzed))
        max_excursions = np.zeros(len(df_analyzed))
        
        # Structural Triple-Barrier Labeling
        for i in range(len(df_analyzed)):
            if signals[i] == 0:
                continue
            
            signal = signals[i]
            entry = closes[i]
            setup_type = df_analyzed['ta_setup'].iloc[i]
            ctx = df_analyzed['engine_context'].iloc[i]
            atr = df_analyzed['ATRr'].iloc[i]
            
            direction_str = 'LONG' if signal == 1 else 'SHORT'
            trade_plan = risk_engine.build_trade_plan(direction_str, entry, setup_type, ctx, atr)
            
            if not trade_plan.get('valid'):
                is_success[i] = 0
                max_excursions[i] = 0
                continue
                
            sl_price = trade_plan['stop_loss']
            tp_price = trade_plan['take_profit']
            
            horizon = min(ML_HORIZON, len(df_analyzed) - i - 1)
            
            max_exc = 0.0
            success = 0
            for j in range(1, horizon + 1):
                h = highs[i+j]
                l = lows[i+j]
                
                if signal == 1:
                    max_exc = max(max_exc, (h - entry) / entry)
                    if l <= sl_price:
                        success = 0
                        break
                    if h >= tp_price:
                        success = 1
                        break
                elif signal == -1:
                    max_exc = max(max_exc, (entry - l) / entry)
                    if h >= sl_price:
                        success = 0
                        break
                    if l <= tp_price:
                        success = 1
                        break
            
            is_success[i] = success
            max_excursions[i] = max_exc
            
        df_analyzed['is_success'] = is_success
        df_analyzed['max_excursion'] = max_excursions
        
        trades_only = df_analyzed[df_analyzed['ta_signal'] != 0].copy()
        all_trades.append(trades_only)

    if not all_trades:
        logger.error("Не удалось собрать данные ни по одной монете.")
        return

    combined_trades = pd.concat(all_trades, ignore_index=True)
    if 'timestamp' in combined_trades.columns:
        combined_trades = combined_trades.sort_values('timestamp').reset_index(drop=True)
        
    total_signals = len(combined_trades)
    successful = combined_trades['is_success'].sum()
    failed = total_signals - successful
    win_rate = (successful / total_signals * 100) if total_signals > 0 else 0
    signals_per_coin = total_signals / len(SYMBOLS) if len(SYMBOLS) > 0 else 0
    
    logger.info("="*50)
    logger.info("СТАТИСТИКА ОБУЧЕНИЯ (STRUCTURAL TRIPLE BARRIER)")
    logger.info("="*50)
    logger.info(f"Режим: {TRADING_MODE}")
    logger.info(f"Всего TA сигналов (после фильтрации трендом): {total_signals}")
    logger.info(f"Успешных (TP): {successful}")
    logger.info(f"Неуспешных (SL/Time): {failed}")
    logger.info(f"Positive Rate (Win-Rate): {win_rate:.2f}%")
    logger.info(f"Сигналов на монету (в среднем): {signals_per_coin:.1f}")
    logger.info("="*50)



    if len(combined_trades) < 20:
        logger.warning(f"Слишком мало сигналов ({len(combined_trades)}) для обучения.")
        return
        
    logger.info(f"Собрано {len(combined_trades)} сигналов. Запуск AutoML и ансамбля...")

    feature_cols = FEATURE_COLUMNS
    X = combined_trades[feature_cols]
    y = combined_trades['is_success']
    # Splitting into Train, Val, Test with Embargo
    val_split_idx = int(len(X) * 0.6)
    test_split_idx = int(len(X) * 0.8)
    
    train_end_idx = val_split_idx - ML_HORIZON
    val_end_idx = test_split_idx - ML_HORIZON
    
    if train_end_idx <= 0 or val_end_idx <= val_split_idx:
        logger.error("Недостаточно данных для Time-Series Embargo.")
        return
        
    X_train = X.iloc[:train_end_idx]
    y_train = y.iloc[:train_end_idx]
    
    X_val = X.iloc[val_split_idx:val_end_idx]
    y_val = y.iloc[val_split_idx:val_end_idx]
    
    X_test = X.iloc[test_split_idx:]
    y_test = y.iloc[test_split_idx:]
    signals_test = combined_trades['ta_signal'].iloc[test_split_idx:]
    
    pos_count = sum(y_train == 1)
    neg_count = sum(y_train == 0)
    scale_pos = neg_count / pos_count if pos_count > 0 else 1.0
    
    # AutoML: RandomizedSearchCV для XGBoost
    xgb_base = xgb.XGBClassifier(random_state=42, eval_metric='logloss', scale_pos_weight=scale_pos)
    param_dist = {
        'n_estimators': [50, 100],
        'max_depth': [3, 4, 5],
        'learning_rate': [0.01, 0.05, 0.1]
    }
    
    try:
        tscv = TimeSeriesSplit(n_splits=3, gap=ML_HORIZON)
    except TypeError:
        tscv = TimeSeriesSplit(n_splits=3)
        
    try:
        search = RandomizedSearchCV(xgb_base, param_distributions=param_dist, n_iter=3, cv=tscv, random_state=42)
        search.fit(X_train, y_train)
        best_xgb = search.best_estimator_
        logger.info("AutoML подобрал лучшие параметры XGBoost.")
    except ValueError as e:
        logger.warning(f"Недостаточно данных для AutoML ({e}). Обучаем XGBoost со стандартными параметрами.")
        best_xgb = xgb_base
        best_xgb.fit(X_train, y_train)

    # Ансамбль
    ensemble = VotingClassifier(estimators=[
        ('xgb', best_xgb), 
        ('rf', RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, class_weight='balanced')),
        ('gb', GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42))
    ], voting='soft')
    
    ensemble.fit(X_train, y_train)
    
    # Dynamic Threshold Search on Validation Set
    probs_val = ensemble.predict_proba(X_val)[:, 1]
    best_f1 = 0
    best_thresh = 0.5
    for thresh in np.arange(0.3, 0.8, 0.05):
        preds = (probs_val >= thresh).astype(int)
        f1 = f1_score(y_val, preds, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = thresh
            
    # Final Metrics on Test Set (OOS)
    probs_test = ensemble.predict_proba(X_test)[:, 1]
    final_preds = (probs_test >= best_thresh).astype(int)
    
    acc = accuracy_score(y_test, final_preds)
    prec = precision_score(y_test, final_preds, zero_division=0)
    rec = recall_score(y_test, final_preds, zero_division=0)
    pr_auc = average_precision_score(y_test, probs_test)
    
    logger.info("="*50)
    logger.info("--- ML Metrics (OOS Test Set with Embargo) ---")
    logger.info(f"Best Threshold (from Val Set): {best_thresh:.2f}")
    logger.info(f"Accuracy: {acc * 100:.2f}%")
    logger.info(f"Precision: {prec * 100:.2f}%")
    logger.info(f"Recall: {rec * 100:.2f}%")
    logger.info(f"F1 Score: {f1_score(y_test, final_preds, zero_division=0):.4f}")
    logger.info(f"PR-AUC: {pr_auc:.4f}")
    
    # LONG / SHORT Specific Metrics
    for direction, sig_val in [("LONG", 1.0), ("SHORT", -1.0)]:
        mask = (signals_test == sig_val)
        if mask.sum() > 0:
            y_t_dir = y_test[mask]
            preds_dir = final_preds[mask]
            probs_dir = probs_test[mask]
            
            d_acc = accuracy_score(y_t_dir, preds_dir)
            d_prec = precision_score(y_t_dir, preds_dir, zero_division=0)
            d_rec = recall_score(y_t_dir, preds_dir, zero_division=0)
            d_f1 = f1_score(y_t_dir, preds_dir, zero_division=0)
            
            logger.info(f"[{direction}] Acc: {d_acc*100:.1f}%, Prec: {d_prec*100:.1f}%, Rec: {d_rec*100:.1f}%, F1: {d_f1:.4f}")
    logger.info("="*50)

    # Расчет вероятностей ИИ для всех сделок выборки
    combined_trades['ml_prob'] = ensemble.predict_proba(combined_trades[feature_cols])[:, 1]

    # Детальная статистика по сетапам с AVG SCORE и AVG ML PROB
    logger.info("="*105)
    logger.info("ДЕТАЛИЗАЦИЯ ПО СЕТАПАМ PRICE ACTION (LONG / SHORT)")
    logger.info("="*105)
    logger.info(f"{'СЕТАП':<24} | {'НАПР':<5} | {'СИГНАЛЫ':<7} | {'WIN':<4} | {'LOSS':<4} | {'WIN RATE':<8} | {'СРЕД. ДВИЖ':<10} | {'SCORE':<5} | {'ML PROB':<7}")
    logger.info("-" * 105)
    
    if 'ta_setup' in combined_trades.columns:
        for (setup_name, sig_dir), grp in combined_trades.groupby(['ta_setup', 'ta_signal']):
            dir_str = "LONG" if sig_dir == 1 else "SHORT"
            n_sig = len(grp)
            n_win = int(grp['is_success'].sum())
            n_loss = n_sig - n_win
            w_rate = (n_win / n_sig * 100) if n_sig > 0 else 0
            avg_exc = grp['max_excursion'].mean() * 100 if 'max_excursion' in grp.columns else 0
            avg_score = grp['SETUP_SCORE'].mean() if 'SETUP_SCORE' in grp.columns else 0
            avg_prob = grp['ml_prob'].mean() if 'ml_prob' in grp.columns else 0
            logger.info(f"{setup_name:<24} | {dir_str:<5} | {n_sig:<7} | {n_win:<4} | {n_loss:<4} | {w_rate:>7.1f}% | +{avg_exc:>6.2f}% | {avg_score:>5.1f} | {avg_prob:>7.2f}")
    logger.info("="*105)

    # Регрессия для предсказания TP
    winning_trades = combined_trades[combined_trades['is_success'] == 1]
    if len(winning_trades) > 10:
        X_reg = winning_trades[feature_cols]
        y_reg = winning_trades['max_excursion']
        regressor = RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42)
        regressor.fit(X_reg, y_reg)
        logger.info("Модель предсказания TP (Regressor) обучена.")
    else:
        regressor = None
        
    model_data = {
        'ensemble': ensemble,
        'regressor': regressor,
        'threshold': best_thresh
    }
    
    joblib.dump(model_data, MODEL_FILE)
    logger.info(f"🧠 ИИ V3 (Ансамбль + TP Регрессор) успешно сохранен в файл: {MODEL_FILE}")

if __name__ == "__main__":
    train_ai()
