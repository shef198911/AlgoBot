with open('entry_gate.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "logger.info(" in line and "logger.info" not in lines[i-1]:
        # We found a logger.info(
        # Look ahead to see if it's ENTRY CHECK
        is_entry = False
        for j in range(i, i+15):
            if j < len(lines) and "ENTRY CHECK" in lines[j]:
                is_entry = True
                break
        
        if is_entry:
            # Inject the if statement
            indent = line[:len(line) - len(line.lstrip())]
            lines[i] = indent + "if LOG_ENTRY_GATE and do_log:\n" + indent + "    " + line.lstrip()
            # indent all subsequent lines until the closing parenthesis
            for j in range(i+1, len(lines)):
                lines[j] = "    " + lines[j]
                if ")" in lines[j]:
                    break

with open('entry_gate.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
    
print("Patched by line manipulation.")
