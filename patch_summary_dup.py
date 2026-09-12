with open('G:/AlgoBot/train_model.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "logger.info(f\"Успешные (TP): {successful}\")" in line:
        pass
    elif "successful" in line and "logger.info" in line:
        pass
    elif "{failed}" in line:
        pass
    elif "(STRUCTURAL TRIPLE BARRIER)" in line and "ИТОГИ АНАЛИЗА БАЗЫ" not in line:
        skip = True
    
    if skip and "logger.info(\"=\"*50)" in line:
        skip = False
        continue
    
    if not skip and "successful" not in line and "failed" not in line:
        new_lines.append(line)

with open('G:/AlgoBot/train_model.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
