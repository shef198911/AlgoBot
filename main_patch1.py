import time
from config import logger, SYMBOLS, TIMEFRAME, TRADE_SIZE_USDT, API_KEY, API_SECRET, USE_TESTNET, ML_PROBABILITY_THRESHOLD
from data_fetcher import DataFetcher
from strategy_ta import TAStrategy
from ml_filter import MLFilter
from executor import TraderExecutor
from telegram_notifier import TelegramNotifier
import os

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
    logger.info("Бот переходит в цикл мониторинга...")

    while True:
        try:
            # Проверка флага мягкого завершения
            if os.path.exists("stop.flag"):
                active_positions = [sym for sym in SYMBOLS if executor.check_position_status(sym)]
                if not active_positions:
                    logger.info("✅ Все сделки закрыты. Бот плавно завершает работу.")
                    os.remove("stop.flag")
                    break
                else:
                    logger.info(f"⏳ Режим завершения. Ожидание закрытия сделок: {active_positions}")
                    time.sleep(15)
                    continue

            for symbol in SYMBOLS:
                if executor.check_position_status(symbol):
                    logger.debug(f"[{symbol}] Бот находится в открытой сделке. Ожидание закрытия...")
                    continue

                # Кулдаун: чтобы не спамить после закрытия сделки, ждем хотя бы немного, 
                # но так как это сложно реализовать без стейт-машины, мы просто будем полагаться на ИИ.
                # Если ИИ строгий, он и так не пустит в сделку.

                # Шаг 1: Получаем рыночные данные
                df = fetcher.get_historical_klines(symbol, TIMEFRAME, limit=1000)
                if df is None:
                    continue

                # Шаг 2: Бот №1 (Теханализ) генерирует сигнал и признаки
                analyzed_data = ta_bot.generate_features_and_signals(df)
                if analyzed_data is None or analyzed_data.empty:
                    continue

                current_state = analyzed_data.iloc[-1]
                
                # Duplicate Signal Protection
                current_time = current_state['timestamp']
                if last_processed_candle[symbol] == current_time:
                    continue

                ta_signal = current_state['ta_signal']
                current_price = current_state['close']
                atr_value = current_state.get('ATRr', 0)
                setup_type = current_state.get('engine_setup')
                engine_context = current_state.get('engine_context')

                if ta_signal != 0:
                    last_processed_candle[symbol] = current_time
                    side_str = 'buy' if ta_signal == 1 else 'sell'
                    
                    # Проверка глобального тренда
                    trend = fetcher.check_global_trend(symbol)
                        # Validate with Strict Entry Gate
                        from entry_gate import EntryGate
                        is_valid, reject_reason = EntryGate.validate(current_state, trend, symbol)
                        if not is_valid:
                            logger.info(f"[{symbol}] Entry Gate REJECTED: {reject_reason}")
                            continue
                        logger.debug(f"[{symbol}] Сигнал {side_str.upper()} отменен: идет против глобального тренда.")
                        continue
                        
                    setup_name = current_state.get('ta_setup', 'Сигнал')
                    dist_res = current_state.get('DIST_RES_PCT', 0) * 100
                    dist_sup = current_state.get('DIST_SUP_PCT', 0) * 100
                    sr_info = f"Запас до сопротивления: +{dist_res:.1f}%" if side_str == 'buy' else f"Запас до поддержки: -{dist_sup:.1f}%"
                    
                    logger.info(f"[{symbol}] [Бот 1 - Теханализ] Сигнал {side_str.upper()}! Сетап: {setup_name} ({sr_info}). Цена: {current_price}")

                    # Шаг 4: Бот №2 (ИИ) фильтрует сигнал.
                    is_approved, ai_confidence, dynamic_tp = ml_bot.evaluate_signal(current_state)
                    
                    if is_approved:
                        tp_text = f"{dynamic_tp*100:.2f}% (Динамический)" if dynamic_tp else "Стандартный"
                        msg_approved = f"✅ <b>Сигнал ОДОБРЕН ИИ</b>\nМонета: {symbol}\nСетап: {setup_name}\nТип: {side_str.upper()}\nВход: {current_price}\n{sr_info}\nУверенность ИИ: {ai_confidence*100:.1f}%\nТейк-Профит ИИ: {tp_text}\n\nОтправляю ордер..."
                        logger.info(f"[{symbol}] [Бот 2 - ИИ] Сигнал ОДОБРЕН. Уверенность: {ai_confidence:.2f}. TP: {tp_text}")
                        tg.send_message(msg_approved)
                        
                        # Расчет суммы входа (Авто-реинвестирование)
                        trade_amount = TRADE_SIZE_USDT
                        from config import USE_COMPOUNDING, COMPOUND_PCT
                        if USE_COMPOUNDING:
                            try:
                                balance = fetcher.exchange.fetch_balance()
                                usdt_bal = balance['total'].get('USDT', 0.0)
                                trade_amount = usdt_bal * (COMPOUND_PCT / 100.0)
                                logger.info(f"[{symbol}] Авто-реинвестирование: {COMPOUND_PCT}% от {usdt_bal:.2f} = {trade_amount:.2f} USDT")
                            except Exception as e:
                                logger.error(f"Ошибка получения баланса для реинвестирования: {e}")
                        
                        # Шаг 5: Исполнение
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
                        breakdown = f" ({ml_bot.last_probs_str})" if getattr(ml_bot, 'last_probs_str', None) else ""
                        logger.warning(f"[{symbol}] [Бот 2 - ИИ] Сигнал ОТКЛОНЕН. Уверенность: {ai_confidence:.2f}{breakdown}. Порог: {ML_PROBABILITY_THRESHOLD}")
            
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
