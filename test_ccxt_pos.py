import ccxt
import json
import config

try:
    exchange = ccxt.binanceusdm({
        'apiKey': config.API_KEY,
        'secret': config.API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future'
        }
    })
    if config.USE_TESTNET:
        exchange.set_sandbox_mode(True)
        
    positions = exchange.fetch_positions()
    for p in positions:
        amt = float(p.get('contracts', 0) or p.get('positionAmt', 0) or p['info'].get('positionAmt', 0))
        if amt != 0:
            print("Found active position!")
            print(json.dumps(p, indent=2))
            break
    else:
        print("No active positions with amt > 0")
        if positions:
            print("First position snippet:")
            print(json.dumps(positions[0], indent=2))
            
except Exception as e:
    print(e)
