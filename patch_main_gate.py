import sys

with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if 'trend = fetcher.check_global_trend(symbol)' in line:
        new_lines.append(line)
        new_lines.append('                        # Validate with Strict Entry Gate\n')
        new_lines.append('                        from entry_gate import EntryGate\n')
        new_lines.append('                        is_valid, reject_reason = EntryGate.validate(current_state, trend, symbol)\n')
        new_lines.append('                        if not is_valid:\n')
        new_lines.append('                            logger.info(f"[{symbol}] Entry Gate REJECTED: {reject_reason}")\n')
        new_lines.append('                            continue\n')
    elif 'if (ta_signal == 1 and trend == -1) or (ta_signal == -1 and trend == 1):' in line:
        # We don't need this basic check anymore, EntryGate handles it
        pass
    elif 'logger.info(f"[{symbol}] Сигнал против глобального тренда. Пропускаем.")' in line:
        pass
    elif 'continue' in line and 'Сигнал против глобального' in lines[i-1]:
        pass
    else:
        new_lines.append(line)

with open('main_patch1.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
