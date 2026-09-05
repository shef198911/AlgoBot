import sys

with open('market_structure.py', 'r', encoding='utf-8') as f:
    source = f.read()

source = source.replace(
    'engine_setup_arr = ["None"] * n',
    'engine_setup_arr = ["None"] * n\n        engine_context_arr = [None] * n'
)

source = source.replace(
    'data[\'engine_setup\'] = engine_setup_arr',
    'data[\'engine_setup\'] = engine_setup_arr\n        data[\'engine_context\'] = engine_context_arr'
)

with open('market_structure.py', 'w', encoding='utf-8') as f:
    f.write(source)
