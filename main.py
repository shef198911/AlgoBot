import time
import os
import concurrent.futures
import threading
from config import logger, SYMBOLS, TIMEFRAME, TRADE_SIZE_USDT, API_KEY, API_SECRET, USE_TESTNET, ML_PROBABILITY_THRESHOLD
from data_fetcher import DataFetcher
from strategy_ta import TAStrategy
from ml_filter import MLFilter
from executor import TraderExecutor
from telegram_notifier import TelegramNotifier
from trend_helper import get_global_trend

execute_lock = threading.Lock()
processed_signals = set()

def process_symbol(symbol, fetcher, ta_bot, ml_bot, executor, tg, last_processed_candle, current_usdt_balance):
    try:
        status = executor.check_position_status(symbol)
        if status is True or status == "UNKNOWN":
            logger.debug(f"[{symbol}] Бот находится в открытой сделке или статус неизвестен. Ожидание...")
            return

        # Шаг 1: Получаем рыночные данные
        df = fetcher.get_historical_klines(symbol, TIMEFRAME, limit=1000)
        if df is None:
            return

        # Шаг 2: Бот №1 (Теханализ) генерирует сигнал и признаки
        trend_str = get_global_trend(fetcher, symbol)
        analyzed_data = ta_bot.generate_features_and_signals(df, htf_trend=trend_str, symbol=symbol, is_live=True)
        if analyzed_data is None or analyzed_data.empty:
            return

        current_state = analyzed_data.iloc[-1]
        
        ta_signal = current_state['ta_signal']
        if ta_signal == 0:
            return
            
        current_time = current_state['timestamp']
        side_str = 'buy' if ta_signal == 1 else 'sell'
        setup_name = current_state.get('ta_setup', 'Сигнал')
        
        # Duplicate Signal Protection
        sig_key = f"{symbol}_{current_time}_{side_str}_{setup_name}"
        with execute_lock:
            if sig_key in processed_signals:
                return
            processed_signals.add(sig_key)
            last_processed_candle[symbol] = current_time

        current_price = current_state['close']
        atr_value = current_state.get('ATRr', 0)
        setup_type = current_state.get('engine_setup')
        engine_context = current_state.get('engine_context')
            
            setup_name = current_state.get('ta_setup', 'Сигнал')
            dist_res = current_state.get('DIST_RES_PCT', 0) * 100
            dist_sup = current_state.get('DIST_SUP_PCT', 0) * 100
            sr_info = f"Запас до сопротивления: +{dist_res:.1f}%" if side_str == 'buy' else f"Запас до поддержки: -{dist_sup:.1f}%"
            
            logger.info(f"[{symbol}] [Бот 1 - Теханализ] Сигнал {side_str.upper()}! Сетап: {setup_name} ({sr_info}). Цена: {current_price}")

            # Шаг 4: Бот №2 (ИИ) фильтрует сигнал.
            is_approved, ai_confidence, dynamic_tp, probs_str = ml_bot.evaluate_signal(current_state)
            
            if is_approved:
                tp_text = f"{dynamic_tp*100:.2f}% (Динамический)" if dynamic_tp else "Стандартный"
                msg_approved = f"✅ <b>Сигнал ОДОБРЕН ИИ</b>\nМонета: {symbol}\nСетап: {setup_name}\nТип: {side_str.upper()}\nВход: {current_price}\n{sr_info}\nУверенность ИИ: {ai_confidence*100:.1f}%\nТейк-Профит ИИ: {tp_text}\n\nОтправляю ордер..."
                logger.info(f"[{symbol}] [Бот 2 - ИИ] Сигнал ОДОБРЕН. Уверенность: {ai_confidence:.2f}. TP: {tp_text}")
                tg.send_message(msg_approved)
                
                # Расчет суммы входа (Авто-реинвестирование)
                trade_amount = TRADE_SIZE_USDT
                from config import USE_COMPOUNDING, COMPOUND_PCT
                if USE_COMPOUNDING and current_usdt_balance is not None:
                    trade_amount = current_usdt_balance * (COMPOUND_PCT / 100.0)
                    logger.info(f"[{symbol}] Авто-реинвестирование: {COMPOUND_PCT}% от {current_usdt_balance:.2f} = {trade_amount:.2f} USDT")
                
                # Шаг 5: Исполнение
                with execute_lock:
                    # Double-check locking
                    double_check_status = executor.check_position_status(symbol)
                    if double_check_status is True or double_check_status == "UNKNOWN":
                        logger.warning(f"[{symbol}] Позиция уже открыта или статус неизвестен (double-check). Пропуск исполнения.")
                        success = False
                    else:
                        success = executor.execute_trade(symbol, side_str, trade_amount, current_price, atr_value=atr_value, dynamic_tp=dynamic_tp, setup_type=setup_type, engine_context=engine_context)
                
                if success:
                    pos = executor.positions.get(symbol, {})
                    sl = pos.get('sl_price', 0)
                    tp = pos.get('tp_price', 0)
                    logger.info(f"[{symbol}] Сделка и защитные ордера успешно выставлены на бирже.")
                    tg.send_message(f"💰 <b>Сделка {side_str.upper()} по {symbol} открыта!</b>\nВход: {current_price}\nСтоп-Лосс: {sl}\nТейк-Профит: {tp}")
                    # Запись в историю
                    with open("trade_history.txt", "a", encoding="utf-8") as f:
                        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {symbol} | {side_str.upper()} | Вход: {current_price}\n")
                else:
                    err_reason = getattr(executor, 'last_error', 'Неизвестная ошибка биржи')
                    logger.error(f"[{symbol}] Не удалось открыть сделку на бирже: {err_reason}")
                    tg.send_message(f"⚠️ <b>Внимание: сбой открытия сделки по {symbol}!</b>\nПричина биржи: <code>{err_reason}</code>")
            else:
                breakdown = f" ({probs_str})" if probs_str else ""
                logger.warning(f"[{symbol}] [Бот 2 - ИИ] Сигнал ОТКЛОНЕН. Уверенность: {ai_confidence:.2f}{breakdown}. Порог: {ML_PROBABILITY_THRESHOLD}")
    except Exception as e:
        logger.error(f"[{symbol}] Ошибка в потоке обработки: {e}")

def main():
    logger.info("=== Запуск Гибридного ИИ Бота ===")
    tg = TelegramNotifier()
    tg.send_message(f"🚀 <b>AlgoBot запущен!</b>\nОтслеживаю монеты: {', '.join(SYMBOLS)}")
    
    if not API_KEY or not API_SECRET:
        logger.error("API ключи не найдены в config.py! Бот будет работать только в режиме анализа (без сделок).")
    
    # 1. Инициализация модулей
    fetcher = DataFetcher(use_testnet=USE_TESTNET, api_key=API_KEY, api_secret=API_SECRET)
    ta_bot = TAStrategy()
    ml_bot = MLFilter()
    executor = TraderExecutor(fetcher.exchange)

    logger.info(f"Символы: {SYMBOLS}, Таймфрейм: {TIMEFRAME}")
    last_processed_candle = {sym: None for sym in SYMBOLS}
    logger.info("Бот переходит в цикл мониторинга (Многопоточный режим)...")

    # Создаем единый пул потоков
    max_workers = min(5, len(SYMBOLS))
    thread_executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    logger.info(f"Пул потоков создан с max_workers={max_workers}")

    while True:
        try:
            # Проверка флага мягкого завершения
            if os.path.exists("stop.flag"):
                active_positions = [sym for sym in SYMBOLS if executor.check_position_status(sym) is True]
                if not active_positions:
                    logger.info("✅ Все сделки закрыты. Бот плавно завершает работу.")
                    os.remove("stop.flag")
                    thread_executor.shutdown(wait=False)
                    break
                else:
                    logger.info(f"⏳ Режим завершения. Ожидание закрытия сделок: {active_positions}")
                    time.sleep(15)
                    continue

            # Получение баланса ОДИН раз за цикл, если включено авто-реинвестирование
            current_usdt_balance = None
            from config import USE_COMPOUNDING
            if USE_COMPOUNDING:
                try:
                    balance = fetcher.exchange.fetch_balance()
                    current_usdt_balance = balance['total'].get('USDT', 0.0)
                except Exception as e:
                    logger.error(f"Ошибка получения баланса для реинвестирования: {e}")

            # Многопоточная обработка пар
            futures = {
                thread_executor.submit(
                    process_symbol, 
                    sym, fetcher, ta_bot, ml_bot, executor, tg, last_processed_candle, current_usdt_balance
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
