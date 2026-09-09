import sys

def fix_regex():
    p = 'G:/AlgoBot/desktop_app.py'
    with open(p, 'r', encoding='utf-8') as f:
        code = f.read()

    old_regex = r"message = re.sub(r'^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2},\d+\s\[.*?\]\s.*?:\s', '', message)"
    new_regex = r"message = re.sub(r'^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2},\d+\s\[.*?\]\s(?:[a-zA-Z_0-9]+:\s)?', '', message)"
    
    if old_regex in code:
        code = code.replace(old_regex, new_regex)
        print("Regex patched!")
    else:
        print("Regex NOT FOUND!")

    with open(p, 'w', encoding='utf-8') as f:
        f.write(code)

fix_regex()
