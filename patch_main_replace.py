with open('G:/AlgoBot/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = r'with open("trade_history.txt", "a", encoding="utf-8") as f:' + '\n' + r'                f.write(f"{time.strftime(' + r"\'%Y-%m-%d %H:%M:%S\'" + r')} | {symbol} | {side_str.upper()} | Вход: {current_price}\n")'

target = '            with open("trade_history.txt", "a", encoding="utf-8") as f:\n                f.write(f"{time.strftime(\'%Y-%m-%d %H:%M:%S\')} | {symbol} | {side_str.upper()} | Вход: {current_price}\\n")'

replacement = '            time_str = time.strftime("%Y-%m-%d %H:%M:%S")\n            with open("trade_history.txt", "a", encoding="utf-8") as f:\n                f.write(f"{time_str} | {symbol} | {side_str.upper()} OPEN | Вход: {current_price:.5f} | SL: {sl:.5f} | TP: {tp:.5f}\\n")'

if target in content:
    content = content.replace(target, replacement)
    with open('G:/AlgoBot/main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced perfectly.")
else:
    print("Target not found.")
