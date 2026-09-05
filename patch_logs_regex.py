import re

with open('entry_gate.py', 'r', encoding='utf-8') as f:
    source = f.read()

# Replace logger.info unconditionally logging
reject_pattern = r"(logger\.info\(\s*f.*?ENTRY CHECK REJECT.*?REASON=\{reject_reason\}\\n\"\s*\))"
pass_pattern = r"(logger\.info\(\s*f.*?ENTRY CHECK PASS.*?ENTRY_GATE=PASS\\n\"\s*\))"

source = re.sub(reject_pattern, r"if LOG_ENTRY_GATE and do_log:\n                \1", source, flags=re.DOTALL)
source = re.sub(pass_pattern, r"if LOG_ENTRY_GATE and do_log:\n            \1", source, flags=re.DOTALL)

with open('entry_gate.py', 'w', encoding='utf-8') as f:
    f.write(source)

print("Patched.")
