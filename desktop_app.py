import asyncio
import flet as ft
import subprocess
import threading
import os
import re
import json
import time
import atexit
from data_fetcher import DataFetcher
from config import API_KEY, API_SECRET, USE_TESTNET

# ──────────────────────────────────────────────────
#  Цвета и константы дизайн-системы
# ──────────────────────────────────────────────────
C_BG           = "#0D1117"
C_SURFACE      = "#161B22"
C_SURFACE2     = "#1C2333"
C_BORDER       = "#30363D"
C_TEXT         = "#E6EDF3"
C_TEXT_DIM     = "#8B949E"
C_GREEN        = "#3FB950"
C_RED          = "#F85149"
C_ORANGE       = "#D29922"
C_BLUE         = "#58A6FF"
C_PURPLE       = "#BC8CFF"
C_CYAN         = "#39D2C0"

class AlgoBotStrategyUI:
    def __init__(self, page: ft.Page, strategy_id: str, quote: str):
        self.page = page
        self.strategy_id = strategy_id
        self.quote_asset = quote
        self.history_file = f"trade_history_{self.strategy_id}.txt"
        self.config_file = "config.py"
        self.state_file = f"live_state_{self.strategy_id}.json"
        
        self.bot_process = None
        self._cached_tickers = None
        self._is_refreshing_positions = False
        self._log_counter = 0
        
        atexit.register(self.emergency_kill_bot)
        
        self.fetcher = DataFetcher(use_testnet=USE_TESTNET, api_key=API_KEY, api_secret=API_SECRET)
        
        self.raw_logs = []
        self.active_log_filter = "ALL"
        
        self.read_config()
        self.build_ui()
        
        threading.Thread(target=self.fetch_balance, daemon=True).start()
        self.page.run_task(self.update_positions_loop)
        self.page.run_task(self.update_history_loop)
        self.update_analytics()

    # ──────────────────────────────────────────────
    #  Config I/O
    # ──────────────────────────────────────────────
    def read_config(self):
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                content = f.read()
            mode_match = re.search(r'TRADING_MODE\s*=\s*"([^"]+)"', content)
            self.current_mode = mode_match.group(1) if mode_match else "NORMAL"
            risk_match = re.search(r'RISK_MODE\s*=\s*"([^"]+)"', content)
            self.current_risk = risk_match.group(1) if risk_match else "BALANCED"
            try:
                self.current_trade_size_mode = re.search(r'TRADE_SIZE_MODE\s*=\s*"([^"]+)"', content).group(1)
            except Exception:
                self.current_trade_size_mode = "AUTO"
            try:
                self.current_base_risk = re.search(r'BASE_RISK_PCT\s*=\s*([0-9.]+)', content).group(1)
            except Exception:
                try:
                    self.current_base_risk = re.search(r'TRADE_SIZE_USDT\s*=\s*([0-9.]+)', content).group(1)
                except Exception:
                    self.current_base_risk = "1.0"
            lev_match = re.search(r'LEVERAGE\s*=\s*([0-9]+)', content)
            self.current_lev = lev_match.group(1) if lev_match else "20"
            cap_match = re.search(r'MAX_CAPITAL_USDT\s*=\s*([0-9.]+)', content)
            self.current_cap = cap_match.group(1) if cap_match else "500.0"
            self.current_sl = re.search(r'STOP_LOSS_PCT\s*=\s*([0-9.]+)', content).group(1)
            self.current_tp = re.search(r'TAKE_PROFIT_PCT\s*=\s*([0-9.]+)', content).group(1)
            self.current_use_atr = "USE_ATR = True" in content
            self.current_use_trail = "USE_TRAILING = True" in content
            self.current_use_comp = "USE_COMPOUNDING = True" in content
            comp_match = re.search(r'COMPOUND_PCT\s*=\s*([0-9.]+)', content)
            self.current_comp_pct = comp_match.group(1) if comp_match else "2.0"
        except Exception:
            self.current_mode = "NORMAL"
            self.current_risk = "BALANCED"
            self.current_trade_size_mode = "AUTO"
            self.current_base_risk = "1.0"
            self.current_lev = "20"
            self.current_cap = "500.0"
            self.current_sl = "0.02"
            self.current_tp = "0.04"
            self.current_use_atr = False
            self.current_use_trail = True
            self.current_use_comp = False
            self.current_comp_pct = "2.0"

    def apply_auto_settings(self, e=None):
        mode = self.dd_mode.value
        risk = self.dd_risk.value
        if mode == "SCALPING":
            presets = {"ЭКОНОМ": ("0.3","0.6"), "БАЛАНС": ("0.5","1.0"), "АГРЕССИВ": ("1.0","2.0")}
        else:
            presets = {"ЭКОНОМ": ("1.0","2.0"), "БАЛАНС": ("2.0","4.0"), "АГРЕССИВ": ("3.0","6.0")}
        sl, tp = presets.get(risk, ("2.0","4.0"))
        self.input_sl.value = sl
        self.input_tp.value = tp
        try:
            self.page.update()
        except Exception:
            pass
        self.log_message(f"[ВНИМАНИЕ] Режим {mode}, Риск {risk}. Сохраните настройки!", "warning")

    def save_config(self, e=None):
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                content = f.read()
            new_size = float(self.input_base_risk.value or 0.0)
            mode_risk = self.dd_trade_size_mode.value
            new_lev = int(self.input_lev.value or 20)
            new_cap = float(self.input_cap.value or 0.0)
            new_sl = float(self.input_sl.value or 0.0) / 100.0
            new_tp = float(self.input_tp.value or 0.0) / 100.0
            new_atr = "True" if self.sw_atr.value else "False"
            new_trail = "True" if self.sw_trail.value else "False"
            new_comp = "True" if self.sw_comp.value else "False"
            new_comp_pct = float(self.input_comp_pct.value or 0.0)
            risk_map = {"ЭКОНОМ": "CONSERVATIVE", "БАЛАНС": "BALANCED", "АГРЕССИВ": "AGGRESSIVE"}
            current_risk_eng = risk_map.get(self.dd_risk.value, "BALANCED")
            content = re.sub(r'TRADING_MODE\s*=\s*"[^"]+"', f'TRADING_MODE = "{self.dd_mode.value}"', content)
            content = re.sub(r'RISK_MODE\s*=\s*"[^"]+"', f'RISK_MODE = "{current_risk_eng}"', content)
            ml_thresholds = {"CONSERVATIVE": "0.65", "BALANCED": "0.55", "AGGRESSIVE": "0.50"}
            content = re.sub(r'ML_PROBABILITY_THRESHOLD\s*=\s*[0-9.]+', f'ML_PROBABILITY_THRESHOLD = {ml_thresholds[current_risk_eng]}', content)
            
            content = re.sub(r'TRADE_SIZE_MODE\s*=\s*"[^"]+"', f'TRADE_SIZE_MODE = "{mode_risk}"', content)
            content = re.sub(r'BASE_RISK_PCT\s*=\s*[0-9.]+', f'BASE_RISK_PCT = {new_size}', content)
            content = re.sub(r'TRADE_SIZE_USDT\s*=\s*[0-9.]+', f'BASE_RISK_PCT = {new_size}', content)
            
            content = re.sub(r'LEVERAGE\s*=\s*[0-9]+', f'LEVERAGE = {new_lev}', content)
            content = re.sub(r'MAX_CAPITAL_USDT\s*=\s*[0-9.]+', f'MAX_CAPITAL_USDT = {new_cap}', content)
            content = re.sub(r'STOP_LOSS_PCT\s*=\s*[0-9.]+', f'STOP_LOSS_PCT = {new_sl}', content)
            content = re.sub(r'TAKE_PROFIT_PCT\s*=\s*[0-9.]+', f'TAKE_PROFIT_PCT = {new_tp}', content)
            content = re.sub(r'USE_ATR\s*=\s*(True|False)', f'USE_ATR = {new_atr}', content)
            content = re.sub(r'USE_TRAILING\s*=\s*(True|False)', f'USE_TRAILING = {new_trail}', content)
            content = re.sub(r'USE_COMPOUNDING\s*=\s*(True|False)', f'USE_COMPOUNDING = {new_comp}', content)
            content = re.sub(r'COMPOUND_PCT\s*=\s*[0-9.]+', f'COMPOUND_PCT = {new_comp_pct}', content)
            with open(self.config_file, "w", encoding="utf-8") as f:
                f.write(content)
            self.log_message("[СИСТЕМА] Настройки успешно сохранены.", "info")
            self.btn_save_text.value = "Сохранено ✓"
            self.btn_save.bgcolor = C_GREEN
            try:
                self.page.update()
            except Exception:
                pass
            def reset_btn():
                time.sleep(1.5)
                self.btn_save_text.value = "Сохранить"
                self.btn_save.bgcolor = C_BLUE
                try:
                    self.page.update()
                except Exception:
                    pass
            threading.Thread(target=reset_btn, daemon=True).start()
            return True
        except Exception as e:
            self.log_message(f"[ОШИБКА] Не удалось сохранить конфигурацию: {e}", "error")
            self.btn_save_text.value = "Ошибка ✕"
            self.btn_save.bgcolor = C_RED
            try:
                self.page.update()
            except Exception:
                pass
            return False

    def train_ai(self, e=None):
        if self.bot_process is not None:
            self.log_message("[ОШИБКА] Сначала остановите торговлю перед запуском обучения!", "error")
            return
        
        # 1. Synchronously save config and verify before starting training (Requirement 11)
        save_ok = self.save_config()
        if not save_ok:
            self.log_message("[ОШИБКА] Обучение отменено: не удалось сохранить файл конфигурации!", "error")
            return

        self.btn_train.disabled = True
        self.btn_train_text.value = "Обучение..."
        self.btn_train.bgcolor = C_SURFACE2
        try:
            self.page.update()
        except Exception:
            pass
        self.log_message("[СИСТЕМА] Конфигурация сохранена. Запуск обучения ИИ...", "info")
        
        def run_train():
            import sys
            base_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(base_dir, "train_model.py")
            process = subprocess.Popen(
                [sys.executable, "-u", script_path], cwd=base_dir,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in process.stdout:
                self.log_message(line.strip())
            process.wait()
            if process.returncode == 0:
                self.log_message("[СИСТЕМА] Обучение завершено! Модель успешно обновлена.", "success")
                self.btn_train_text.value = "Готово ✓"
                self.btn_train.bgcolor = C_GREEN
            else:
                self.log_message(f"[ОШИБКА] Обучение завершилось с кодом {process.returncode}", "error")
                self.btn_train_text.value = "Ошибка ✕"
                self.btn_train.bgcolor = C_RED
            try:
                self.page.update()
            except Exception:
                pass
            time.sleep(2)
            self.btn_train.disabled = False
            self.btn_train_text.value = "Обучить ИИ"
            self.btn_train.bgcolor = C_ORANGE
            try:
                self.page.update()
            except Exception:
                pass

        threading.Thread(target=run_train, daemon=True).start()

    # ──────────────────────────────────────────────
    #  UI Layout Helpers
    # ──────────────────────────────────────────────
    def _section_label(self, text, icon=None):
        children = []
        if icon:
            children.append(ft.Icon(icon, size=14, color=C_CYAN))
        children.append(ft.Text(text, size=11, weight=ft.FontWeight.W_700, color=C_TEXT_DIM))
        return ft.Container(
            content=ft.Row(children, spacing=6),
            margin=ft.Margin.only(top=8, bottom=2)
        )

    def _input_group(self, label_text, control):
        return ft.Column([
            ft.Text(label_text, size=12, weight=ft.FontWeight.W_500, color=C_TEXT),
            control
        ], spacing=4)

    def _styled_field(self, value, hint_text="", width=None):
        return ft.TextField(
            value=value,
            hint_text=hint_text,
            hint_style=ft.TextStyle(size=12, color=C_TEXT_DIM),
            width=width,
            dense=True,
            border_color=C_BORDER,
            focused_border_color=C_CYAN,
            cursor_color=C_CYAN,
            text_size=13,
            text_style=ft.TextStyle(size=13, color=C_TEXT),
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            border_radius=6,
            filled=True,
            fill_color=C_SURFACE2,
        )

    def _action_button(self, text, bgcolor, on_click, icon=None, **kwargs):
        return ft.Container(
            content=ft.Row(
                [
                    *(([ft.Icon(icon, size=15, color="#FFFFFF")] if icon else [])),
                    ft.Text(text, size=12, weight=ft.FontWeight.W_600, color="#FFFFFF"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=5,
            ),
            bgcolor=bgcolor,
            border_radius=6,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            on_click=on_click,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
            **kwargs,
        )

    # ──────────────────────────────────────────────
    #  BUILD UI
    # ──────────────────────────────────────────────
    def build_ui(self):
        risk_map_rev = {"CONSERVATIVE": "ЭКОНОМ", "BALANCED": "БАЛАНС", "AGGRESSIVE": "АГРЕССИВ"}

        # Clean structured dropdowns without overlapping label overlays
        self.dd_mode = ft.Dropdown(
            options=[ft.dropdown.Option("NORMAL"), ft.dropdown.Option("SCALPING")],
            value=self.current_mode,
            on_select=self.apply_auto_settings, on_text_change=self.apply_auto_settings,
            dense=True, border_color=C_BORDER, focused_border_color=C_CYAN,
            text_size=13, text_style=ft.TextStyle(size=13, color=C_TEXT),
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=6,
            filled=True, fill_color=C_SURFACE2,
        )
        self.dd_risk = ft.Dropdown(
            options=[ft.dropdown.Option("ЭКОНОМ"), ft.dropdown.Option("БАЛАНС"), ft.dropdown.Option("АГРЕССИВ")],
            value=risk_map_rev.get(self.current_risk, "БАЛАНС"),
            on_select=self.apply_auto_settings, on_text_change=self.apply_auto_settings,
            dense=True, border_color=C_BORDER, focused_border_color=C_CYAN,
            text_size=13, text_style=ft.TextStyle(size=13, color=C_TEXT),
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=6,
            filled=True, fill_color=C_SURFACE2,
        )
        
        self.dd_trade_size_mode = ft.Dropdown(
            options=[ft.dropdown.Option("AUTO"), ft.dropdown.Option("MANUAL")],
            value=self.current_trade_size_mode,
            dense=True, border_color=C_BORDER, focused_border_color=C_CYAN,
            text_size=13, text_style=ft.TextStyle(size=13, color=C_TEXT),
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=6,
            filled=True, fill_color=C_SURFACE2,
        )

        # Styled clean input fields
        self.input_base_risk = self._styled_field(self.current_base_risk)
        self.input_lev = self._styled_field(self.current_lev)
        self.input_cap = self._styled_field(self.current_cap)
        self.input_sl = self._styled_field(str(float(self.current_sl)*100))
        self.input_tp = self._styled_field(str(float(self.current_tp)*100))
        self.input_comp_pct = self._styled_field(self.current_comp_pct)

        # Switches
        self.sw_atr = ft.Switch(label="ATR (динамический SL/TP)", value=self.current_use_atr, active_color=C_CYAN, scale=0.85)
        self.sw_trail = ft.Switch(label="Трейлинг-Стоп", value=self.current_use_trail, active_color=C_CYAN, scale=0.85)
        self.sw_comp = ft.Switch(label="Авто-реинвестирование", value=self.current_use_comp, active_color=C_CYAN, scale=0.85)

        # Buttons with dedicated Text controls to avoid modifying .text on ft.Container (Requirement 12)
        self.btn_save_text = ft.Text("Сохранить", size=12, weight=ft.FontWeight.W_600, color="#FFFFFF", text_align=ft.TextAlign.CENTER)
        self.btn_save = ft.Container(
            content=self.btn_save_text,
            bgcolor=C_BLUE, border_radius=6, height=38,
            on_click=lambda e: threading.Thread(target=self.save_config).start(),
            alignment=ft.Alignment(0, 0),
        )

        self.btn_train_text = ft.Text("Обучить ИИ", size=12, weight=ft.FontWeight.W_600, color="#FFFFFF", text_align=ft.TextAlign.CENTER)
        self.btn_train = ft.Container(
            content=self.btn_train_text,
            bgcolor=C_ORANGE, border_radius=6, height=38,
            on_click=self.train_ai,
            alignment=ft.Alignment(0, 0),
        )

        # Left Sidebar with clear typography and clean columns
        sidebar = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.AUTO_AWESOME, size=20, color=C_CYAN),
                    ft.Text("AlgoBot AI", size=20, weight=ft.FontWeight.W_700, color=C_CYAN),
                ], spacing=6),
                ft.Text("Панель управления и риск-менеджмент", size=11, color=C_TEXT_DIM),
                ft.Divider(color=C_BORDER, height=1),

                self._section_label("ТОРГОВЛЯ", ft.Icons.CANDLESTICK_CHART),
                self._input_group("Тип торговли", self.dd_mode),
                self._input_group("Риск-режим", self.dd_risk),
                self._input_group("Режим объема", self.dd_trade_size_mode),

                self._section_label("КАПИТАЛ", ft.Icons.ACCOUNT_BALANCE_WALLET),
                ft.Row([
                    ft.Column([ft.Text("Баз. риск (%)", size=12, weight=ft.FontWeight.W_500, color=C_TEXT), self.input_base_risk], spacing=4, expand=1),
                    ft.Column([ft.Text("Плечо (x)", size=12, weight=ft.FontWeight.W_500, color=C_TEXT), self.input_lev], spacing=4, expand=1),
                ], spacing=8),
                self._input_group("Лимит капитала ($)", self.input_cap),

                self._section_label("РИСК", ft.Icons.SHIELD),
                ft.Row([
                    ft.Column([ft.Text("Stop-Loss %", size=12, weight=ft.FontWeight.W_500, color=C_TEXT), self.input_sl], spacing=4, expand=1),
                    ft.Column([ft.Text("Take-Profit %", size=12, weight=ft.FontWeight.W_500, color=C_TEXT), self.input_tp], spacing=4, expand=1),
                ], spacing=8),

                self._section_label("PRO ОПЦИИ", ft.Icons.SETTINGS_SUGGEST),
                self.sw_atr,
                self.sw_trail,
                self.sw_comp,
                self._input_group("% реинвестирования", self.input_comp_pct),

                ft.Container(height=6),
                self.btn_save,
                ft.Container(height=2),
                self.btn_train,
            ], scroll=ft.ScrollMode.AUTO, spacing=6),
            width=270,
            padding=14,
            bgcolor=C_SURFACE,
        )

        # ── CENTER ──
        self.lbl_balance = ft.Text("Баланс: загрузка...", size=13, weight=ft.FontWeight.W_600, color=C_TEXT)
        self.lbl_status = ft.Container(
            content=ft.Text("ОСТАНОВЛЕН", size=11, weight=ft.FontWeight.W_700, color=C_RED),
            bgcolor=ft.Colors.with_opacity(0.15, C_RED),
            border_radius=4,
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        )

        header_row = ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET, size=16, color=C_CYAN),
                    self.lbl_balance
                ], spacing=6),
                ft.Row([
                    self.lbl_status,
                    ft.IconButton(ft.Icons.REFRESH, icon_size=16, icon_color=C_TEXT_DIM,
                                  on_click=lambda e: threading.Thread(target=self.fetch_balance).start()),
                ], spacing=6),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            bgcolor=C_SURFACE,
        )

        # Control buttons (Distinguished Stop vs Emergency Kill - Requirement 8)
        self.btn_start = self._action_button("Запустить", C_GREEN, self.start_bot, ft.Icons.PLAY_ARROW)
        self.btn_graceful = self._action_button("Стоп (доработать)", C_ORANGE, self.graceful_stop, ft.Icons.STOP_CIRCLE)
        self.btn_kill = self._action_button("Аварийный Kill", C_RED, self.emergency_kill_bot, ft.Icons.DANGEROUS)

        controls_row = ft.Container(
            content=ft.Row([self.btn_start, self.btn_graceful, self.btn_kill], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(vertical=4),
        )

        # Console toolbar with quick filter chips
        self.filter_chips_row = ft.Row(spacing=4)
        self._build_filter_chips()

        console_toolbar = ft.Container(
            content=ft.Row([
                self.filter_chips_row,
                ft.Row([
                    ft.IconButton(ft.Icons.COPY, icon_size=15, icon_color=C_TEXT_DIM, tooltip="Скопировать",
                                  on_click=lambda e: self._copy_console()),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=15, icon_color=C_TEXT_DIM, tooltip="Очистить",
                                  on_click=lambda e: self._clear_console()),
                    ft.IconButton(ft.Icons.DOWNLOAD, icon_size=15, icon_color=C_TEXT_DIM, tooltip="Скачать лог",
                                  on_click=self.download_console),
                ], spacing=0),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            bgcolor=C_SURFACE2,
            border_radius=ft.BorderRadius(top_left=8, top_right=8, bottom_left=0, bottom_right=0),
        )

        self.console_list = ft.ListView(expand=1, spacing=2, auto_scroll=True, padding=6)
        console_body = ft.Container(
            content=self.console_list,
            expand=True,
            bgcolor=C_BG,
            border_radius=ft.BorderRadius(top_left=0, top_right=0, bottom_left=8, bottom_right=8),
        )

        # History & Analytics
        self.history_list = ft.ListView(expand=1, spacing=3, auto_scroll=True, padding=8)

        self.lbl_stat_trades = ft.Text("Сделок: 0", size=24, weight=ft.FontWeight.W_700, color=C_TEXT)
        self.lbl_stat_winrate = ft.Text("Win-Rate: 0%", size=20, weight=ft.FontWeight.W_600, color=C_TEXT_DIM)
        self.lbl_stat_pnl = ft.Text("PnL: $0.00", size=20, weight=ft.FontWeight.W_600, color=C_TEXT_DIM)
        self.lbl_stat_funnel = ft.Text("Воронка сигналов: загрузка...", size=13, color=C_TEXT_DIM)

        t1_content = ft.Column([console_toolbar, console_body], spacing=0, expand=True)

        t2_content = ft.Container(
            content=self.history_list,
            bgcolor=C_BG, border_radius=8, margin=6, expand=True,
        )

        t3_content = ft.Container(
            content=ft.Column([
                self.lbl_stat_trades,
                ft.Divider(color=C_BORDER),
                self.lbl_stat_winrate,
                self.lbl_stat_pnl,
                ft.Divider(color=C_BORDER),
                self.lbl_stat_funnel,
                ft.Container(height=6),
                self._action_button("Обновить статистику", C_BLUE, lambda e: self.update_analytics(), ft.Icons.REFRESH),
            ], spacing=8),
            padding=16,
        )

        tabs = ft.Tabs(
            selected_index=0, length=3,
            content=ft.Column([
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Консоль"),
                        ft.Tab(label="История"),
                        ft.Tab(label="Аналитика"),
                    ],
                    indicator_color=C_CYAN,
                    label_color=C_TEXT,
                    unselected_label_color=C_TEXT_DIM,
                ),
                ft.TabBarView(expand=True, controls=[t1_content, t2_content, t3_content])
            ]),
            expand=1,
        )

        center = ft.Column([header_row, controls_row, ft.Container(content=tabs, expand=True, padding=ft.Padding.symmetric(horizontal=8))], expand=True, spacing=2)

        # ── RIGHT SIDEBAR (POSITIONS) ──
        self.positions_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

        right_sidebar = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Позиции", size=15, weight=ft.FontWeight.W_700, color=C_TEXT),
                    ft.Container(
                        content=ft.Text("Отчёт", size=11, color=C_BLUE),
                        on_click=self.download_detailed_trades,
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(color=C_BORDER),
                self.positions_col,
            ], expand=True, spacing=6),
            width=270,
            padding=12,
            bgcolor=C_SURFACE,
        )

        self.main_layout = ft.Row([sidebar, ft.Container(content=center, expand=True), right_sidebar], expand=True, spacing=0)

    # ──────────────────────────────────────────────
    #  LOG FILTERING & COMPACT LOG CARDS
    # ──────────────────────────────────────────────
    def _build_filter_chips(self):
        filters = [
            ("ALL", "Все"),
            ("SIGNALS", "Сигналы"),
            ("REJECTS", "Отказы"),
            ("TRADES", "Сделки"),
            ("ERRORS", "Ошибки"),
            ("RECOVERY", "Recovery")
        ]
        self.filter_chips_row.controls.clear()
        for code, label in filters:
            is_active = (self.active_log_filter == code)
            chip = ft.Container(
                content=ft.Text(label, size=10, weight=ft.FontWeight.W_600, color=C_TEXT if is_active else C_TEXT_DIM),
                bgcolor=ft.Colors.with_opacity(0.2, C_CYAN) if is_active else ft.Colors.TRANSPARENT,
                border=ft.Border.all(1, C_CYAN if is_active else C_BORDER),
                border_radius=4,
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                on_click=lambda e, f_code=code: self._set_log_filter(f_code),
            )
            self.filter_chips_row.controls.append(chip)

    def _set_log_filter(self, filter_code):
        self.active_log_filter = filter_code
        self._build_filter_chips()
        self._render_filtered_console()
        try:
            self.page.update()
        except Exception:
            pass

    def _categorize_log(self, message):
        msg_upper = message.upper()
        if "[GO]" in message or "ОТКРЫТА" in msg_upper or "ЗАКРЫТА" in msg_upper or "СДЕЛКА" in msg_upper:
            return "TRADES"
        elif "RECOVERY" in msg_upper or "ТРЕЙЛИНГ" in msg_upper or "EMERGENCY" in msg_upper or "UNKNOWN" in msg_upper:
            return "RECOVERY"
        elif "[ОШИБКА" in message or "ERROR" in msg_upper or "CRITICAL" in msg_upper or "СБОЙ" in msg_upper or "ОТКЛОНЕНА RISK" in msg_upper:
            return "ERRORS"
        elif "[V]" in message or "ОДОБРЕН" in msg_upper or "1-Й СЛОЙ: ДА" in msg_upper:
            return "SIGNALS"
        elif "[X]" in message or "1-Й СЛОЙ: НЕТ" in msg_upper or "2-Й СЛОЙ: НЕТ" in msg_upper:
            return "REJECTS"
        else:
            return "ALL"

    def _parse_log_entry(self, message):
        category = self._categorize_log(message)
        symbol = self._extract_symbol(message)
        
        if "[GO]" in message:
            return (category, "🚀", C_GREEN, symbol, message.replace("[GO]","").strip(), C_GREEN)
        elif "[V]" in message:
            return (category, "✓", C_CYAN, symbol, message.replace("[V]","").strip(), C_CYAN)
        elif category == "ERRORS":
            return (category, "🚨", C_RED, symbol, message, C_RED)
        elif category == "RECOVERY":
            return (category, "⚡", C_PURPLE, symbol, message.replace("[СИСТЕМА]","").strip(), C_PURPLE)
        elif "[X]" in message:
            return (category, "✕", C_TEXT_DIM, symbol, message.replace("[X]","").strip(), C_TEXT_DIM)
        elif "[ВНИМАНИЕ]" in message or "WARNING" in message.upper():
            return (category, "⚡", C_ORANGE, symbol, message.replace("[ВНИМАНИЕ]","").strip(), C_ORANGE)
        elif "[СИСТЕМА]" in message or "[INFO]" in message:
            return (category, "ℹ", C_BLUE, symbol, message.replace("[СИСТЕМА]","").replace("[INFO]","").strip(), C_BLUE)
        else:
            return (category, None, None, symbol, message, C_TEXT_DIM)

    def _extract_symbol(self, msg):
        m = re.search(r'([A-Z0-9]{2,10}/USDT)', msg)
        return m.group(1) if m else None

    def _build_log_card(self, log_item):
        icon = log_item.get('icon')
        icon_bg = log_item.get('icon_bg', C_SURFACE2)
        symbol = log_item.get('symbol')
        text = log_item.get('text', '')
        color = log_item.get('color', C_TEXT_DIM)
        ts = log_item.get('timestamp', '')
        count = log_item.get('count', 1)
        category = log_item.get('category', 'ALL')

        # Extract rejection / error reason for compact chip
        reason_match = re.search(r'\(([^)]+)\)', text)
        clean_text = text
        reason_tag = None
        if reason_match:
            reason_tag = reason_match.group(1).replace("1-й слой: ", "").replace("2-й слой: ", "").strip()
            clean_text = re.sub(r'\([^)]+\)', '', text).strip()

        row_elements = []

        if icon:
            row_elements.append(
                ft.Container(
                    content=ft.Text(icon, size=11, weight=ft.FontWeight.W_700, color=color, text_align=ft.TextAlign.CENTER),
                    width=20, height=20,
                    border_radius=4,
                    bgcolor=ft.Colors.with_opacity(0.18, icon_bg if icon_bg else color),
                    alignment=ft.Alignment(0, 0),
                )
            )

        row_elements.append(ft.Text(ts, size=10, color=C_TEXT_DIM))

        if symbol:
            base_token = symbol.split("/")[0].lower() if "/" in symbol else "btc"
            icon_url = f"https://cdn.jsdelivr.net/gh/atomiclabs/cryptocurrency-icons@1a63530be6e374711a8554f31b17e4cb92c25fa5/128/color/{base_token}.png"
            row_elements.append(ft.Image(src=icon_url, width=16, height=16, border_radius=8, error_content=ft.Container(width=0, height=0)))
            row_elements.append(ft.Text(symbol, size=11, weight=ft.FontWeight.W_700, color=C_TEXT))
            
            # Clean up redundant symbol in text if it exists
            if clean_text.startswith(symbol):
                clean_text = clean_text[len(symbol):].strip()
                if clean_text.startswith("-"):
                    clean_text = clean_text[1:].strip()

        if reason_tag:
            chip_color = C_RED if ("ERROR" in reason_tag or "FAIL" in reason_tag or category == "ERRORS") else (C_ORANGE if "TREND" in reason_tag else C_TEXT_DIM)
            row_elements.append(
                ft.Container(
                    content=ft.Text(reason_tag, size=9, weight=ft.FontWeight.W_600, color=chip_color),
                    bgcolor=ft.Colors.with_opacity(0.15, chip_color),
                    border_radius=3,
                    padding=ft.Padding.symmetric(horizontal=4, vertical=1),
                )
            )

        # Truncated details
        if clean_text:
            row_elements.append(
                ft.Text(clean_text, size=11, color=color, overflow=ft.TextOverflow.ELLIPSIS, max_lines=1, expand=True)
            )

        # Repeating count multiplier badge
        if count > 1:
            row_elements.append(
                ft.Container(
                    content=ft.Text(f"×{count}", size=10, weight=ft.FontWeight.W_700, color=C_ORANGE),
                    bgcolor=ft.Colors.with_opacity(0.2, C_ORANGE),
                    border_radius=3,
                    padding=ft.Padding.symmetric(horizontal=4, vertical=1),
                )
            )

        card_bg = ft.Colors.with_opacity(0.10, C_RED) if category == "ERRORS" else C_SURFACE2

        return ft.Container(
            content=ft.Row(row_elements, spacing=6, alignment=ft.MainAxisAlignment.START),
            bgcolor=card_bg,
            border_radius=4,
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        )

    def _render_filtered_console(self):
        self.console_list.controls.clear()
        f = self.active_log_filter
        for item in self.raw_logs:
            if f == "ALL" or item.get('category') == f:
                self.console_list.controls.append(self._build_log_card(item))

    def log_message(self, message, force_tag=None):
        message = re.sub(r'\x1b\[.*?m', '', message)
        message = re.sub(r'^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2},\d+\s\[.*?\]\s(?:[a-zA-Z_0-9]+:\s)?', '', message)
        message = re.sub(r'^\[\d{2}/\d{2}/\d{2}\s\d{2}:\d{2}:\d{2}\]\s\w+\s+', '', message)

        if not message.strip():
            return
        if message.startswith("===") or message.startswith("---"):
            return

        if force_tag == "success":
            message = "[V] " + message if "[V]" not in message and "[GO]" not in message else message
        elif force_tag == "error":
            message = "[X] " + message if "[X]" not in message and "[ОШИБКА" not in message else message
        elif force_tag == "warning":
            message = "[ВНИМАНИЕ] " + message if "[ВНИМАНИЕ]" not in message else message
        elif force_tag == "info":
            message = "[СИСТЕМА] " + message if "[СИСТЕМА]" not in message else message

        category, icon, icon_bg, symbol, text, color = self._parse_log_entry(message)
        ts = time.strftime("%H:%M:%S")

        # Repeating reject deduplication
        if category == "REJECTS" and self.raw_logs and self.raw_logs[-1].get('category') == "REJECTS":
            last_item = self.raw_logs[-1]
            if last_item.get('symbol') == symbol and last_item.get('text') == text:
                last_item['count'] += 1
                last_item['timestamp'] = ts
                if self.active_log_filter in ["ALL", "REJECTS"] and self.console_list.controls:
                    self.console_list.controls[-1] = self._build_log_card(last_item)
                    try:
                        self.page.update()
                    except Exception:
                        pass
                return

        log_item = {
            'category': category,
            'icon': icon,
            'icon_bg': icon_bg,
            'symbol': symbol,
            'text': text,
            'color': color,
            'timestamp': ts,
            'count': 1,
            'raw': message
        }
        self.raw_logs.append(log_item)
        if len(self.raw_logs) > 600:
            self.raw_logs = self.raw_logs[-600:]

        if self.active_log_filter == "ALL" or self.active_log_filter == category:
            self.console_list.controls.append(self._build_log_card(log_item))
            if len(self.console_list.controls) > 300:
                self.console_list.controls = self.console_list.controls[-300:]

        try:
            self.page.update()
        except Exception:
            pass

    def _clear_console(self):
        self.raw_logs.clear()
        self.console_list.controls.clear()
        try:
            self.page.update()
        except Exception:
            pass

    def _copy_console(self):
        lines = [item.get('raw', '') for item in self.raw_logs]
        text = "\n".join(lines)
        try:
            import subprocess
            subprocess.run(['clip.exe'], input=text.encode('utf-8'), check=True)
            self.log_message("[СИСТЕМА] Логи скопированы в буфер обмена.", "info")
        except Exception as e:
            self.log_message(f"[ОШИБКА] Сбой буфера обмена: {e}", "error")

    # ──────────────────────────────────────────────
    #  Бизнес-логика и рендеринг позиций
    # ──────────────────────────────────────────────
    def fetch_balance(self):
        try:
            self.lbl_balance.value = "Баланс: загрузка..."
            try:
                self.page.update()
            except Exception:
                pass
            balance = self.fetcher.exchange.fetch_balance()
            if 'free' in balance and 'USDT' in balance['free']:
                usdt = float(balance['free']['USDT'])
            else:
                usdt = -1.0
            self.lbl_balance.value = f"{usdt:,.2f} USDT"
        except Exception as e:
            self.lbl_balance.value = "Ошибка загрузки"
            self.log_message(f"[ОШИБКА] Баланс: {e}", "error")
        finally:
            try:
                self.page.update()
            except Exception:
                pass

    async def update_positions_loop(self):
        while True:
            if not self._is_refreshing_positions:
                self._is_refreshing_positions = True
                threading.Thread(target=self._fetch_and_render_positions, daemon=True).start()
            await asyncio.sleep(5)

    def _fetch_and_render_positions(self):
        try:
            positions = self.fetcher.exchange.fetch_positions()
            
            st = {}
            if os.path.exists(self.state_file):
                try:
                    with open(self.state_file, 'r', encoding='utf-8') as f:
                        st = json.load(f)
                except Exception:
                    pass
            
            active_pos = []
            for pos in (positions or []):
                if not pos['symbol'].endswith(self.quote_asset) and not pos['symbol'].endswith(f"{self.quote_asset}:USDT"):
                    continue
                amt_str = pos.get('info', {}).get('positionAmt', pos.get('contracts', 0))
                contracts = abs(float(amt_str)) if amt_str else 0.0
                if contracts > 0:
                    symbol = pos['symbol']
                    clean_sym = symbol.split(':')[0]
                    side = pos['side'].upper()
                    entry = float(pos.get('entryPrice', 0.0))
                    unrealized_pnl = float(pos.get('unrealizedPnl', 0.0))
                    leverage = float(pos.get('info', {}).get('leverage', 1))
                    margin = (entry * contracts) / leverage if leverage else (entry * contracts)
                    roe_pct = (unrealized_pnl / margin) * 100 if margin > 0 else 0.0
                    
                    sl, tp = None, None
                    sl_ok = False
                    tp_ok = False
                    match_key = clean_sym if clean_sym in st else (symbol if symbol in st else None)
                    if match_key:
                        val_sl = st[match_key].get('sl_price')
                        val_tp = st[match_key].get('tp_price')
                        if val_sl and float(val_sl) > 0:
                            sl = str(val_sl)
                            sl_ok = bool(st[match_key].get('sl_order_id'))
                        if val_tp and float(val_tp) > 0:
                            tp = str(val_tp)
                            tp_ok = bool(st[match_key].get('tp_order_id'))
                    
                    mark_price = float(pos.get('markPrice') or pos.get('info', {}).get('markPrice') or entry)
                    current_price = mark_price

                    active_pos.append({
                        'symbol': symbol, 'clean_sym': clean_sym, 'side': side,
                        'entry': entry, 'current_price': current_price,
                        'pnl': unrealized_pnl, 'roe_pct': roe_pct,
                        'sl': sl or "—", 'tp': tp or "—", 
                        'sl_ok': sl_ok, 'tp_ok': tp_ok,
                        'contracts': contracts, 'leverage': leverage,
                        'margin': margin
                    })
            
            self.positions_col.controls.clear()
            if not active_pos:
                self.positions_col.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.INBOX, size=18, color=C_TEXT_DIM),
                            ft.Text("Нет активных позиций", size=11, color=C_TEXT_DIM),
                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                        alignment=ft.Alignment(0, 0),
                        padding=12,
                        bgcolor=C_SURFACE2,
                        border_radius=6
                    )
                )
            else:
                for p in active_pos:
                    side_color = C_GREEN if p['side'] == "LONG" else C_RED
                    pnl_color = C_GREEN if p['pnl'] >= 0 else C_RED
                    sl_badge_color = C_GREEN if p['sl_ok'] else C_RED
                    tp_badge_color = C_GREEN if p['tp_ok'] else C_ORANGE
                    
                    card = ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Row([
                                    ft.Text(p['clean_sym'], size=13, weight=ft.FontWeight.W_700, color=C_TEXT),
                                    ft.Text(f"{int(p['leverage'])}x", size=10, color=C_TEXT_DIM),
                                ], spacing=4),
                                ft.Container(
                                    content=ft.Text(p['side'], size=9, weight=ft.FontWeight.W_700, color=side_color),
                                    bgcolor=ft.Colors.with_opacity(0.15, side_color),
                                    border_radius=3, padding=ft.Padding.symmetric(horizontal=5, vertical=2),
                                ),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Row([
                                ft.Text(f"Вход: {p['entry']:.4f}", size=10, color=C_TEXT_DIM),
                                ft.Icon(ft.Icons.ARROW_FORWARD, size=10, color=C_TEXT_DIM),
                                ft.Text(f"{p['current_price']:.4f}", size=10, color=C_TEXT),
                            ], spacing=4),
                            ft.Row([
                                ft.Container(
                                    content=ft.Text(f"SL: {p['sl']} ({'OK' if p['sl_ok'] else 'RECOVERY'})", size=9, color=sl_badge_color),
                                    bgcolor=ft.Colors.with_opacity(0.12, sl_badge_color),
                                    border_radius=3, padding=ft.Padding.symmetric(horizontal=4, vertical=1),
                                ),
                                ft.Container(
                                    content=ft.Text(f"TP: {p['tp']} ({'OK' if p['tp_ok'] else '...' })", size=9, color=tp_badge_color),
                                    bgcolor=ft.Colors.with_opacity(0.12, tp_badge_color),
                                    border_radius=3, padding=ft.Padding.symmetric(horizontal=4, vertical=1),
                                ),
                            ], spacing=6),
                            ft.Row([
                                ft.Text(f"{p['pnl']:+.2f} $ ({p['roe_pct']:+.1f}%)", size=12, weight=ft.FontWeight.W_700, color=pnl_color),
                                ft.Container(
                                    content=ft.Text("Закрыть", size=10, color=C_RED, weight=ft.FontWeight.W_600),
                                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                    bgcolor=ft.Colors.with_opacity(0.12, C_RED),
                                    border_radius=4,
                                    on_click=lambda e, sym=p['symbol'], side=p['side'], cnt=p['contracts']: threading.Thread(target=self.close_position_manual, args=(sym, side, cnt)).start(),
                                ),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ], spacing=4),
                        bgcolor=C_SURFACE2,
                        border_radius=8,
                        padding=8,
                    )
                    self.positions_col.controls.append(card)
            
            try:
                self.page.update()
            except Exception:
                pass
        except Exception:
            pass
        finally:
            self._is_refreshing_positions = False

    def close_position_manual(self, symbol, side, contracts):
        try:
            close_side = "sell" if side.upper() == "LONG" else "buy"
            self.log_message(f"[СИСТЕМА] Закрытие позиции {symbol}...", "info")
            try:
                self.fetcher.exchange.cancel_all_orders(symbol)
            except Exception:
                pass
            self.fetcher.exchange.create_market_order(symbol, close_side, contracts, params={'reduceOnly': True})
            self.log_message(f"[V] Позиция {symbol} закрыта!", "success")
            self._fetch_and_render_positions()
            self.fetch_balance()
        except Exception as e:
            self.log_message(f"[ОШИБКА] {symbol}: {e}", "error")

    def update_analytics(self):
        if os.path.exists("analytics_data.json"):
            try:
                with open("analytics_data.json", "r", encoding="utf-8") as f:
                    trades = json.load(f)
                total = len(trades)
                wins = sum(1 for t in trades if t.get('is_win', False))
                pnl = sum(t.get('profit_usdt', t.get('pnl', 0)) for t in trades)
                win_rate = (wins / total * 100) if total > 0 else 0
                self.lbl_stat_trades.value = f"Сделок: {total}"
                self.lbl_stat_winrate.value = f"Win-Rate: {win_rate:.1f}%"
                self.lbl_stat_winrate.color = C_GREEN if win_rate >= 50 else C_RED
                sign = "+" if pnl >= 0 else ""
                self.lbl_stat_pnl.value = f"PnL: {sign}${pnl:.2f}"
                self.lbl_stat_pnl.color = C_GREEN if pnl >= 0 else C_RED
                
                from entry_gate import get_funnel_summary
                funnel = get_funnel_summary()
                funnel_text = (
                    f"Воронка: Сигналы={funnel.get('SIGNAL_FOUND',0)} "
                    f"-> Gate={funnel.get('ENTRY_GATE_PASS',0)}/{funnel.get('ENTRY_GATE_FAIL',0)} "
                    f"-> ML={funnel.get('ML_PASS',0)}/{funnel.get('ML_FAIL',0)} "
                    f"-> Risk={funnel.get('RISK_PASS',0)}/{funnel.get('RISK_FAIL',0)} "
                    f"-> Ордера={funnel.get('ORDER_SUCCESS',0)}/{funnel.get('ORDER_FAIL',0)}"
                )
                self.lbl_stat_funnel.value = funnel_text
                self.page.update()
            except Exception as e:
                self.log_message(f"Ошибка аналитики: {e}")

    async def update_history_loop(self):
        last_hist = ""
        while True:
            if os.path.exists(self.history_file):
                try:
                    with open(self.history_file, "r", encoding="utf-8") as f:
                        hist = f.read()
                    if hist != last_hist:
                        last_hist = hist
                        self.history_list.controls.clear()
                        for line in reversed(hist.split('\n')):
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
                            )
                        self.page.update()
                except Exception:
                    pass
            await asyncio.sleep(5)

    def start_bot(self, e=None):
        if os.path.exists("stop.flag"):
            try:
                os.remove("stop.flag")
            except Exception:
                pass
        if self.bot_process is None:
            self.log_message("[СИСТЕМА] Запуск торгового ядра...", "info")
            self.lbl_status.content = ft.Text("АКТИВЕН", size=11, weight=ft.FontWeight.W_700, color=C_GREEN)
            self.lbl_status.bgcolor = ft.Colors.with_opacity(0.15, C_GREEN)
            self.btn_start.visible = False
            self.btn_graceful.visible = True
            self.btn_kill.visible = True
            self.page.update()
            import sys
            base_dir = os.path.dirname(os.path.abspath(__file__))
            main_script = os.path.join(base_dir, "main.py")
            self.bot_process = subprocess.Popen(
                [sys.executable, "-u", main_script, "--strategy", self.strategy_id, "--quote", self.quote_asset], cwd=base_dir,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            threading.Thread(target=self.read_output, daemon=True).start()

    def read_output(self):
        while self.bot_process is not None:
            try:
                line = self.bot_process.stdout.readline()
                if not line:
                    break
                self.log_message(line.strip())
            except Exception:
                break
        self.handle_bot_stop()

    def graceful_stop(self, e=None):
        """
        Graceful Stop (Requirement 8): Stops new entries while keeping position management,
        SL/TP protection, recovery, and trailing active until all positions are flat.
        """
        self.log_message("[ВНИМАНИЕ] Режим плавного завершения. Новые входы остановлены, открытые позиции продолжают управляться до закрытия.", "warning")
        with open("stop.flag", "w") as f:
            f.write("stop")
        self.lbl_status.content = ft.Text("ЗАВЕРШЕНИЕ...", size=11, weight=ft.FontWeight.W_700, color=C_ORANGE)
        self.lbl_status.bgcolor = ft.Colors.with_opacity(0.15, C_ORANGE)
        self.btn_graceful.visible = False
        try:
            self.page.update()
        except Exception:
            pass

    def emergency_kill_bot(self, e=None):
        """
        Explicit Emergency Kill action: Terminates the local Python bot process immediately.
        Orders on exchange remain placed.
        """
        if self.bot_process is not None:
            self.log_message("[СИСТЕМА] Принудительный сброс (Kill) локального процесса. Позиции на бирже остаются защищенными SL/TP.", "warning")
            self.bot_process.kill()
            self.bot_process = None
            self.handle_bot_stop()

    def handle_bot_stop(self):
        self.lbl_status.content = ft.Text("ОСТАНОВЛЕН", size=11, weight=ft.FontWeight.W_700, color=C_RED)
        self.lbl_status.bgcolor = ft.Colors.with_opacity(0.15, C_RED)
        self.btn_start.visible = True
        self.btn_graceful.visible = False
        self.btn_kill.visible = False
        try:
            self.page.update()
        except Exception:
            pass

    def download_console(self, e=None):
        lines = [item.get('raw', '') for item in self.raw_logs]
        if lines:
            out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded_console_log.txt")
            with open(out, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.log_message(f"[СИСТЕМА] Лог сохранён: {out}", "info")
        else:
            self.log_message("[ОШИБКА] Лог пуст.", "error")

    def download_detailed_trades(self, e=None):
        import shutil
        base = os.path.dirname(os.path.abspath(__file__))
        if os.path.exists("detailed_trades.jsonl"):
            out = os.path.join(base, "downloaded_detailed_trades.jsonl")
            shutil.copy("detailed_trades.jsonl", out)
            self.log_message(f"[СИСТЕМА] Отчёт сохранён: {out}", "info")
        elif os.path.exists("trade_history.txt"):
            out = os.path.join(base, "downloaded_trade_report.txt")
            shutil.copy("trade_history.txt", out)
            self.log_message(f"[СИСТЕМА] Отчёт сохранён: {out}", "info")
        else:
            self.log_message("[ОШИБКА] Отчёт не создан.", "error")


class AlgoBotMainApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "AlgoBot AI - Dual Strategy"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor = C_BG
        self.page.theme = ft.Theme(
            color_scheme_seed=ft.Colors.INDIGO,
            visual_density=ft.VisualDensity.COMPACT,
        )
        self.page.padding = 0
        self.page.window.width = 1320
        self.page.window.height = 880
        self.page.fonts = {"Inter": "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"}
        self.v1_ui = AlgoBotStrategyUI(page, "v1", "USDT")
        self.v2_ui = AlgoBotStrategyUI(page, "v2", "USDC")

        tabs = ft.Tabs(
            selected_index=0, length=2,
            content=ft.Column([
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="V1 (USDT - ML)"),
                        ft.Tab(label="V2 (USDC - Donchian)"),
                    ],
                    indicator_color=C_CYAN,
                    label_color=C_TEXT,
                    unselected_label_color=C_TEXT_DIM,
                ),
                ft.TabBarView(expand=True, controls=[self.v1_ui.main_layout, self.v2_ui.main_layout])
            ]),
            expand=1,
        )

        self.page.add(tabs)


def main(page: ft.Page):
    app = AlgoBotMainApp(page)


if __name__ == '__main__':
    ft.app(target=main)
