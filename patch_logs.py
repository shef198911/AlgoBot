import sys

with open('entry_gate.py', 'r', encoding='utf-8') as f:
    source = f.read()

old_reject = """            logger.info(
                f"\\n[ENTRY CHECK REJECT]\\n"
                f"SYMBOL={symbol} {direction_str}\\n"
                f"SETUP={eng_setup}\\n"
                f"SCORE={score}\\n"
                f"STRUCTURE_BULL={is_bullish_struct} BEAR={is_bearish_struct}\\n"
                f"GLOBAL_TREND={global_trend}\\n"
                f"ENTRY_GATE=FAIL\\n"
                f"REASON={reject_reason}\\n"
            )"""

new_reject = """            if symbol != "UNKNOWN":
                logger.info(
                    f"\\n[ENTRY CHECK REJECT]\\n"
                    f"SYMBOL={symbol} {direction_str}\\n"
                    f"SETUP={eng_setup}\\n"
                    f"SCORE={score}\\n"
                    f"STRUCTURE_BULL={is_bullish_struct} BEAR={is_bearish_struct}\\n"
                    f"GLOBAL_TREND={global_trend}\\n"
                    f"ENTRY_GATE=FAIL\\n"
                    f"REASON={reject_reason}\\n"
                )"""

old_pass = """        logger.info(
            f"\\n[ENTRY CHECK PASS]\\n"
            f"SYMBOL={symbol} {direction_str}\\n"
            f"SETUP={eng_setup}\\n"
            f"SCORE={score}\\n"
            f"STRUCTURE_BULL={is_bullish_struct} BEAR={is_bearish_struct}\\n"
            f"GLOBAL_TREND={global_trend}\\n"
            f"ENTRY_GATE=PASS\\n"
        )"""

new_pass = """        if symbol != "UNKNOWN":
            logger.info(
                f"\\n[ENTRY CHECK PASS]\\n"
                f"SYMBOL={symbol} {direction_str}\\n"
                f"SETUP={eng_setup}\\n"
                f"SCORE={score}\\n"
                f"STRUCTURE_BULL={is_bullish_struct} BEAR={is_bearish_struct}\\n"
                f"GLOBAL_TREND={global_trend}\\n"
                f"ENTRY_GATE=PASS\\n"
            )"""

source = source.replace(old_reject, new_reject).replace(old_pass, new_pass)

with open('entry_gate.py', 'w', encoding='utf-8') as f:
    f.write(source)
