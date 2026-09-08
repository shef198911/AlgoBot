import re

def patch_desktop_app():
    with open('G:/AlgoBot/desktop_app.py', 'r', encoding='utf-8') as f:
        code = f.read()

    # 1. Patch `_build_log_card`
    old_build = """        if symbol:
            row_elements.append(ft.Text(symbol, size=11, weight=ft.FontWeight.W_700, color=C_TEXT))

        if reason_tag:"""

    new_build = """        if symbol:
            base_token = symbol.split("/")[0].lower() if "/" in symbol else "btc"
            icon_url = f"https://cdn.jsdelivr.net/gh/atomiclabs/cryptocurrency-icons@1a63530be6e374711a8554f31b17e4cb92c25fa5/128/color/{base_token}.png"
            row_elements.append(ft.Image(src=icon_url, width=16, height=16, border_radius=8, error_content=ft.Container(width=0, height=0)))
            row_elements.append(ft.Text(symbol, size=11, weight=ft.FontWeight.W_700, color=C_TEXT))
            
            # Clean up redundant symbol in text if it exists
            if clean_text.startswith(symbol):
                clean_text = clean_text[len(symbol):].strip()
                if clean_text.startswith("-"):
                    clean_text = clean_text[1:].strip()

        if reason_tag:"""

    if old_build in code:
        code = code.replace(old_build, new_build)
        print("_build_log_card patched.")
    else:
        print("_build_log_card not found. It might be already patched.")

    # 2. Patch history tab parsing
    old_history_loop = """                        self.history_list.controls.clear()
                        for line in hist.split('\\n'):
                            if line.strip():
                                color = C_TEXT_DIM
                                if "[V]" in line or "ЗАКРЫТА" in line: color = C_GREEN
                                elif "[X]" in line or "ОТКЛОНЕН" in line: color = C_RED
                                self.history_list.controls.append(
                                    ft.Container(
                                        content=ft.Text(line, size=11, color=color, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                                        bgcolor=C_SURFACE2,
                                        border_radius=4,
                                    )
                                )"""

    new_history_loop = """                        self.history_list.controls.clear()
                        for line in reversed(hist.split('\\n')):
                            if not line.strip(): continue
                            
                            color = C_TEXT_DIM
                            parts = line.split(" | ")
                            
                            if len(parts) >= 3:
                                ts_str = parts[0]
                                symbol = parts[1].strip()
                                action = parts[2].strip()
                                details = " | ".join(parts[3:]).strip()
                                
                                base_token = symbol.split("/")[0].lower() if "/" in symbol else "btc"
                                icon_url = f"https://cdn.jsdelivr.net/gh/atomiclabs/cryptocurrency-icons@1a63530be6e374711a8554f31b17e4cb92c25fa5/128/color/{base_token}.png"
                                
                                if action in ["BUY", "SELL", "OPEN"]:
                                    action_color = C_GREEN if action in ["BUY", "OPEN"] else C_RED
                                    action_icon = "▶"
                                elif action == "EXIT":
                                    action_color = C_PURPLE
                                    action_icon = "⏹"
                                    if "PnL: -" in details:
                                        color = C_RED
                                    else:
                                        color = C_GREEN
                                elif action == "REJECT":
                                    action_color = C_ORANGE
                                    action_icon = "✕"
                                else:
                                    action_color = C_TEXT_DIM
                                    action_icon = "•"
                                    
                                row_elements = [
                                    ft.Text(ts_str, size=10, color=C_TEXT_DIM),
                                    ft.Image(src=icon_url, width=16, height=16, border_radius=8, error_content=ft.Container(width=0, height=0)),
                                    ft.Text(symbol, size=11, weight=ft.FontWeight.W_700, color=C_TEXT),
                                    ft.Container(
                                        content=ft.Text(f"{action_icon} {action}", size=9, weight=ft.FontWeight.W_700, color=action_color),
                                        bgcolor=ft.Colors.with_opacity(0.15, action_color),
                                        padding=ft.Padding.symmetric(horizontal=4, vertical=2),
                                        border_radius=4
                                    ),
                                    ft.Text(details, size=11, color=color, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, expand=True)
                                ]
                                
                                content_widget = ft.Row(row_elements, spacing=8, alignment=ft.MainAxisAlignment.START)
                            else:
                                content_widget = ft.Text(line, size=11, color=color, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)

                            self.history_list.controls.append(
                                ft.Container(
                                    content=content_widget,
                                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                    bgcolor=C_SURFACE2,
                                    border_radius=6,
                                )
                            )"""

    if old_history_loop in code:
        code = code.replace(old_history_loop, new_history_loop)
        print("History loop patched.")
    else:
        print("History loop not found.")

    with open('G:/AlgoBot/desktop_app.py', 'w', encoding='utf-8') as f:
        f.write(code)

patch_desktop_app()
