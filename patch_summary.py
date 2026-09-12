import re

with open('G:/AlgoBot/train_model.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace summary part
pattern = re.compile(r'total_signals = len\(combined_trades\).*?logger\.info\("="\*50\)', re.DOTALL)

replacement_summary = """total_signals = len(combined_trades)
    n_tp = (combined_trades['outcome'] == 'TP').sum()
    n_sl = (combined_trades['outcome'] == 'SL').sum()
    n_time = (combined_trades['outcome'] == 'TIMEOUT').sum()
    win_rate = (n_tp / total_signals * 100) if total_signals > 0 else 0
    signals_per_coin = total_signals / len(SYMBOLS) if len(SYMBOLS) > 0 else 0
    
    logger.info("="*50)
    logger.info("ИТОГИ АНАЛИЗА БАЗЫ (STRUCTURAL TRIPLE BARRIER)")
    logger.info("="*50)
    logger.info(f"Режим: {TRADING_MODE}")
    logger.info(f"Всего валидных сигналов (после EntryGate/Risk/Trend): {total_signals}")
    logger.info(f"Успешные (TP): {n_tp}")
    logger.info(f"Стопы (SL): {n_sl}")
    logger.info(f"Таймауты (TIMEOUT): {n_time}")
    logger.info(f"Positive Rate (Win-Rate): {win_rate:.2f}%")
    logger.info(f"Среднее число сигналов (на монету): {signals_per_coin:.1f}")
    logger.info("="*50)"""

content = re.sub(pattern, replacement_summary, content)

with open('G:/AlgoBot/train_model.py', 'w', encoding='utf-8') as f:
    f.write(content)
