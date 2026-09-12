import re
import html

with open('G:/AlgoBot/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = "f\"Причина: <code>{err_reason}</code>\""

# Let's import html at the top of the file if not there.
if "import html" not in content:
    content = content.replace("import os\n", "import os\nimport html\n")

# Let's replace the f-string.
# Note: since the string is Russian in the file, it might be scrambled in my console but the file is utf-8.
# Let's use regex to find the tg.send_message part and replace err_reason with html.escape(str(err_reason))

def patch_main(text):
    lines = text.split('\n')
    new_lines = []
    for line in lines:
        if 'f"Причина: <code>{err_reason}</code>"' in line:
            new_lines.append(line.replace('{err_reason}', '{html.escape(str(err_reason))}'))
        elif 'f"??ؐ?: <code>{err_reason}</code>"' in line:
            new_lines.append(line.replace('{err_reason}', '{html.escape(str(err_reason))}'))
        elif '<code>{err_reason}</code>' in line:
            new_lines.append(line.replace('{err_reason}', '{html.escape(str(err_reason))}'))
        else:
            new_lines.append(line)
    return '\n'.join(new_lines)

new_content = patch_main(content)
with open('G:/AlgoBot/main.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("Escaped err_reason in main.py")
