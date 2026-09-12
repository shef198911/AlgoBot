import time
import os
import html
import argparse
import concurrent.futures
import threading
from config import (
    logger, SYMBOLS, TIMEFRAME, BASE_RISK_PCT, 
    API_KEY, API_SECRET, USE_TESTNET, USE_COMPOUNDING, COMPOUND_PCT
)
from data_fetcher import DataFetcher
from ml_filter import MLFilter
from executor import TraderExecutor
from telegram_notifier import TelegramNotifier
from entry_gate import record_funnel_event, get_funnel_summary

execute_lock = threading.Lock()
signal_tracker_lock = threading.Lock()
# Signal state machine: sig_key -> {'status': str, 'candle_time': timestamp, 'attempts': int}
# States: CANDIDATE, ML_REJECTED, EXECUTION_FAILED, EXECUTED, UNKNOWN
signal_states = {}

def process_symbol(symbol, fetcher, ta_bot, ml_bot, executor, tg, last_processed_candle, current_usdt_balance, positions_snapshot, strategy_id="v1"):
    try:
        status = executor.check_position_status(symbol, cached_positions=positions_snapshot)
        if status is True or status == "UNKNOWN":
            logger.debug(f"[{symbol}] Бот находится в открытой сделке или статус неизвестен. Ожидание...")
            return

        # Шаг 1: Получаем рыночные данные
        df = fetcher.get_historical_klines(symbol, TIMEFRAME, limit=1000)
        if df is None or df.empty:
            return

        # Шаг 2: Бот №1 (Теханализ) генерирует сигнал и признаки
        if strategy_id == "v1":
            from trend_helper import get_global_trend
            trend_str = get_global_trend(fetcher, symbol)
            analyzed_data = ta_bot.generate_features_and_signals(df, htf_trend=trend_str, symbol=symbol, is_live=True)
        else:
            # Для V2 глобальный тренд не требуется
            analyzed_data = ta_bot.generate_features_and_signals(df, symbol=symbol, is_live=True)
            
        if analyzed_data is None or analyzed_data.empty:
            return

        current_state = analyzed_data.iloc[-1]
        
        ta_signal = current_state.get('ta_signal', 0)
        if ta_signal == 0:
            return
            
        current_time = current_state.get('timestamp')
        side_str = 'buy' if ta_signal == 1 else 'sell'
        setup_name = current_state.get('ta_setup', 'Сигнал')
        
        # Signal State Machine (Requirement 6)
        sig_key = (
            current_state.get("timestamp"),
            symbol,
            side_str,
            setup_name
        )
        with signal_tracker_lock:
            if sig_key in signal_states:
                return
                
            signal_states[sig_key] = {'status': 'CANDIDATE', 'candle_time': current_time, 'attempts': 1}
            if len(signal_states) > 1000:
                first_key = next(iter(signal_states))
                del signal_states[first_key]
            last_processed_candle[symbol] = current_time

        current_price = float(current_state.get('close', 0.0))
        atr_value = float(current_state.get('ATRr', 0.0))
        setup_type = current_state.get('engine_setup')
        engine_context = current_state.get('engine_context')
            
        dist_res = float(current_state.get('DIST_RES_PCT', 0.0)) * 100
        dist_sup = float(current_state.get('DIST_SUP_PCT', 0.0)) * 100
        sr_info = f"Запас до сопротивления: +{dist_res:.1f}%" if side_str == 'buy' else f"Запас до поддержки: -{dist_sup:.1f}%"
        logger.info(f"[V] {symbol} - 1-й слой: ДА ({setup_name}, {side_str.upper()}) -> Передаю на 2-й слой")

        # Шаг 4: Бот №2 (ИИ) фильтрует сигнал
        is_approved, ai_confidence, dynamic_tp, probs_str = ml_bot.evaluate_signal(current_state)
        from diagnostic_tracker import diagnostic_tracker
        diagnostic_tracker.record_ml_prediction(symbol, side_str, is_approved, ai_confidence)
        
        if not is_approved:
            with signal_tracker_lock:
                if sig_key in signal_states:
                    signal_states[sig_key]['status'] = 'ML_REJECTED'
            record_funnel_event('ML_FAIL')
            logger.warning(f"[X] {symbol} - 1-й слой: ДА - 2-й слой: НЕТ (уверенность {ai_confidence*100:.1f}%)")
            return

        record_funnel_event('ML_PASS')
        tp_text = f"{dynamic_tp*100:.2f}% (Динамический)" if dynamic_tp else "Стандартный"
        msg_approved = f"✅ <b>Сигнал ОДОБРЕН ИИ</b>\nМонета: {symbol}\nСетап: {setup_name}\nТип: {side_str.upper()}\nВход: {current_price}\n{sr_info}\nУверенность ИИ: {ai_confidence*100:.1f}%\nТейк-Профит ИИ: {tp_text}\n\nОтправляю ордер..."
        logger.info(f"[GO] {symbol} - 1-й слой: ДА - 2-й слой: ДА (уверенность {ai_confidence*100:.1f}%) -> Проверяю Risk Engine и размер позиции...")
        tg.send_message(msg_approved)
        
        # 3. Dynamic risk sizing via Capital Manager
        import config
        from capital_manager import compute_risk_budget
        try:
            trade_mode = getattr(config, 'TRADE_SIZE_MODE', 'AUTO')
        except Exception:
            trade_mode = "AUTO"

        # Use effective capital (Requirement 1: min of TRADING_CAPITAL, real balance)
        effective_cap = executor.get_effective_capital()
        if effective_cap <= 0:
            err = "Не удалось определить эффективный капитал (сбой API баланса или нулевой баланс). Блокировка новых сделок (Fail-Closed)."
            logger.error(f"[{symbol}] {err}")
            with signal_tracker_lock:
                if sig_key in signal_states:
                    signal_states[sig_key]['status'] = 'EXECUTION_REJECTED'
            record_funnel_event('RISK_FAIL')
            return

        if trade_mode == "AUTO":
            # Compute risk budget with AI confidence scaling + hard caps (Requirements 3, 6)
            budget = compute_risk_budget(
                effective_capital=effective_cap,
                base_risk_pct=float(getattr(config, 'BASE_RISK_PCT', 1.0)),
                ai_confidence=ai_confidence,
                allocated_margin=sum(pos.get('margin_required', 0.0) for pos in executor.positions.values() if pos.get('margin_required')) + sum(executor.pending_margins.values()),
                positions=executor.positions,
            )
            trade_amount = budget['risk_usdt']
            risk_pct = budget['risk_pct']
            conf_mult = budget['confidence_mult']
            
            if not budget.get('portfolio_risk_ok', True):
                with signal_tracker_lock:
                    if sig_key in signal_states:
                        signal_states[sig_key]['status'] = 'EXECUTION_REJECTED'
                record_funnel_event('RISK_FAIL')
                logger.warning(f"[{symbol}] Общий риск портфеля превышен! Пропуск сделки. Risk USDT: {trade_amount:.2f}")
                return
        else:
            try:
                base_risk_pct = float(getattr(config, 'BASE_RISK_PCT', 1.0)) / 100.0
                if base_risk_pct <= 0:
                    base_risk_pct = 0.01
            except Exception:
                base_risk_pct = 0.01
            risk_pct = base_risk_pct * 100.0
            trade_amount = effective_cap * base_risk_pct
            conf_mult = 1.0

        logger.info(f"[{symbol}] Risk Sizing: AI Confidence {ai_confidence*100:.1f}% (x{conf_mult:.1f}) -> Risk {risk_pct:.2f}%. Risk Amount: {trade_amount:.2f} USDT from {effective_cap:.2f} Effective Cap")
        
        # Шаг 5: Исполнение
        with execute_lock:
            # Double-check locking with fresh position check
            double_check_status = executor.check_position_status(symbol, force_fetch=True)
            if double_check_status is True or double_check_status == "UNKNOWN":
                logger.warning(f"[{symbol}] Позиция уже открыта или статус неизвестен (double-check). Пропуск исполнения.")
                with signal_tracker_lock:
                    if sig_key in signal_states:
                        signal_states[sig_key]['status'] = 'UNKNOWN'
                return

            success = executor.execute_trade(
                symbol, side_str, trade_amount, current_price, 
                atr_value=atr_value, dynamic_tp=dynamic_tp, 
                setup_type=setup_type, engine_context=engine_context, 
                ai_confidence=ai_confidence, probs_str=probs_str, 
                ta_setup=setup_name
            )
        
        with signal_tracker_lock:
            if sig_key in signal_states:
                if success:
                    signal_states[sig_key]['status'] = 'EXECUTED'
                elif getattr(executor, 'last_error', '') == 'UNKNOWN_AMOUNT':
                    signal_states[sig_key]['status'] = 'UNKNOWN'
                elif any(err in getattr(executor, 'last_error', '') for err in ['Лимит капитала', 'Worst-case', 'Рассчитанный объем']):
                    signal_states[sig_key]['status'] = 'EXECUTION_REJECTED'
                else:
                    signal_states[sig_key]['status'] = 'EXECUTION_FAILED'

        if success:
            diagnostic_tracker.record_pass(symbol, 'FINAL')
            record_funnel_event('ORDER_SUCCESS')
            pos = executor.positions.get(symbol, {})
            sl = pos.get('sl_price', 0)
            tp = pos.get('tp_price', 0)
            logger.info(f"[{symbol}] Сделка и защитные ордера успешно выставлены на бирже.")
            tg.send_message(f"💰 <b>Сделка {side_str.upper()} по {symbol} открыта!</b>\nВход: {current_price}\nСтоп-Лосс: {sl}\nТейк-Профит: {tp}")
            time_str = time.strftime("%Y-%m-%d %H:%M:%S")
            with open("trade_history.txt", "a", encoding="utf-8") as f:
                f.write(f"{time_str} | {symbol} | {side_str.upper()} OPEN | Вход: {current_price:.5f} | SL: {sl:.5f} | TP: {tp:.5f}\n")
        else:
            err_reason = getattr(executor, 'last_error', 'Неизвестная ошибка биржи')
            # If not already recorded as RISK_FAIL in executor, record as ORDER_FAIL
            if "отклонена Risk Engine" not in err_reason and "Лимит капитала исчерпан" not in err_reason and "Worst-case risk" not in err_reason:
                record_funnel_event('ORDER_FAIL')
            logger.error(f"[{symbol}] Не удалось открыть сделку на бирже: {err_reason}")
            
            if str(err_reason).startswith("rr_too_low_") or any(
                marker in str(err_reason)
                for marker in [
                    "invalid_risk",
                    "sl_too_",
                    "tp_calc",
                    "RISK",
                    "margin",
                    "portfolio"
                ]
            ):
                reason_source = "Risk Engine"
            else:
                reason_source = "Биржа / Execution"

            tg.send_message(
                f"⚠️ <b>Сделка по {symbol} не открыта</b>\n"
                f"Источник отказа: <b>{reason_source}</b>\n"
                f"Причина: <code>{html.escape(str(err_reason))}</code>"
            )

    except Exception as e:
        logger.error(f"[{symbol}] Ошибка в потоке обработки: {e}")

def get_git_build():
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2
        )
        sha = result.stdout.strip()
        return sha if sha else "unknown"
    except Exception:
        return "unknown"

def main():
    parser = argparse.ArgumentParser(description="AlgoBot Main Runner")
    parser.add_argument("--strategy", type=str, default="v1", choices=["v1", "v2"], help="Strategy to run (v1 or v2)")
    parser.add_argument("--quote", type=str, default="USDT", help="Quote asset to trade (e.g., USDT, USDC)")
    args = parser.parse_args()
    
    strategy_id = args.strategy
    quote_asset = args.quote

    logger.info(f"=== Запуск Гибридного ИИ Бота (Strategy: {strategy_id.upper()}, Quote: {quote_asset}) ===")
    
    BOT_BUILD = get_git_build()
    logger.info("=" * 70)
    logger.info(f"AlgoBot BUILD: {BOT_BUILD}")
    logger.info(f"TRADING_MODE: {TIMEFRAME}")
    logger.info(f"ML threshold from config: {getattr(__import__('config'), 'ML_PROBABILITY_THRESHOLD', None)}")
    logger.info("=" * 70)

    # Filter symbols by quote asset
    active_symbols = [sym for sym in SYMBOLS if sym.endswith(f"/{quote_asset}")]
    if not active_symbols and quote_asset != "USDT":
        # Create symbols dynamically if not in SYMBOLS list
        base_assets = [sym.split("/")[0] for sym in SYMBOLS if "/" in sym]
        active_symbols = [f"{base}/{quote_asset}" for base in base_assets]

    tg = TelegramNotifier()
    tg.send_message(f"🚀 <b>AlgoBot запущен ({strategy_id.upper()})!</b>\nОтслеживаю монеты ({quote_asset}): {', '.join(active_symbols)}")
    
    if not API_KEY or not API_SECRET:
        logger.error("API ключи не найдены в config.py! Бот будет работать только в режиме анализа (без сделок).")
    
    # 1. Инициализация модулей
    fetcher = DataFetcher(use_testnet=USE_TESTNET, api_key=API_KEY, api_secret=API_SECRET)
    
    if strategy_id == "v1":
        from strategy_ta import TAStrategy
        ta_bot = TAStrategy()
    else:
        from strategy_v2 import StrategyV2
        ta_bot = StrategyV2()
        
    ml_bot = MLFilter()
    
    # Calculate working capital for the session
    from config import MAX_CAPITAL_USDT
    if float(MAX_CAPITAL_USDT) > 0:
        session_working_capital = float(MAX_CAPITAL_USDT)
    else:
        session_working_capital = 500.0 # Strict fallback to 500 bot equity, NOT real balance
            
    logger.info(f"Session Working Capital (Bot Equity): {session_working_capital:.2f} USDT")
    
    executor = TraderExecutor(fetcher.exchange, working_capital=session_working_capital)

    logger.info(f"Символы: {active_symbols}, Таймфрейм: {TIMEFRAME}")
    last_processed_candle = {sym: None for sym in active_symbols}
    logger.info("Бот переходит в цикл мониторинга (Многопоточный режим)...")

    # Создаем единый пул потоков
    max_workers = min(5, len(active_symbols))
    thread_executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    logger.info(f"Пул потоков создан с max_workers={max_workers}")

    while True:
        try:
            # Проверка флага мягкого завершения (Graceful Stop - прекращение новых входов + продолжение управления позициями)
            if os.path.exists("stop.flag"):
                active_positions = [sym for sym in SYMBOLS if executor.check_position_status(sym) in [True, "UNKNOWN"]]
                if not active_positions:
                    logger.info("✅ Все сделки закрыты. Бот плавно завершает работу.")
                    os.remove("stop.flag")
                    thread_executor.shutdown(wait=False)
                    break
                else:
                    logger.info(f"⏳ Режим завершения (STOP). Новые входы заблокированы, управление позициями продолжается: {active_positions}")
                    time.sleep(15)
                    continue

            # Получение баланса ОДИН раз за цикл (Requirement 1: effective = min(TRADING_CAPITAL, real))
            current_usdt_balance = -1.0 # default to unknown state
            try:
                balance = fetcher.exchange.fetch_balance()
                if 'free' in balance and 'USDT' in balance['free']:
                    current_usdt_balance = float(balance['free']['USDT'])
                else:
                    logger.error("Свободный баланс (free) USDT не найден в ответе биржи!")
                    current_usdt_balance = -1.0
                executor.update_real_balance(current_usdt_balance)
            except Exception as e:
                logger.error(f"Ошибка получения баланса: {e}")
                executor.update_real_balance(-1.0)

            # Single Position Snapshot per cycle for all 25 coins (Requirement 7)
            positions_snapshot = executor.fetch_all_positions()

            # Многопоточная обработка пар
            futures = {
                thread_executor.submit(
                    process_symbol, 
                    sym, fetcher, ta_bot, ml_bot, executor, tg, 
                    last_processed_candle, current_usdt_balance, positions_snapshot
                ): sym for sym in SYMBOLS
            }
            
            for future in concurrent.futures.as_completed(futures):
                sym = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Необработанная ошибка в потоке для {sym}: {e}")
            
            # Ждем перед следующим опросом 
            time.sleep(15)

        except KeyboardInterrupt:
            logger.info("Остановка бота пользователем.")
            break
        except Exception as e:
            logger.error(f"Непредвиденная ошибка в главном цикле: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
