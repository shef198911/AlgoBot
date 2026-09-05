import unittest
from unittest.mock import MagicMock, patch
import ast
import flet as ft
import desktop_app

class TestDesktopApp(unittest.TestCase):
    def test_no_deprecated_ft_attributes(self):
        with open('desktop_app.py', 'r', encoding='utf-8') as f:
            src = f.read()

        tree = ast.parse(src)
        errors = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                chain = []
                curr = node
                while isinstance(curr, ast.Attribute):
                    chain.append(curr.attr)
                    curr = curr.value
                if isinstance(curr, ast.Name) and curr.id == 'ft':
                    chain.append('ft')
                    parts = list(reversed(chain))[1:]
                    obj = ft
                    for part in parts:
                        if hasattr(obj, part):
                            obj = getattr(obj, part)
                        else:
                            errors.append(f'Line {node.lineno}: ft.{part} does not exist on {obj}')
                            break
        self.assertEqual(errors, [], f'Invalid Flet attributes found: {errors}')

    def test_app_initialization_and_ui(self):
        page = MagicMock(spec=ft.Page)
        page.window = MagicMock()
        page.fonts = {}
        page.add = MagicMock()
        page.update = MagicMock()
        page.run_task = MagicMock()

        with patch('desktop_app.AlgoBotApp.fetch_balance'):
            app = desktop_app.AlgoBotApp(page)

        self.assertIsNotNone(app)
        self.assertIsNotNone(app.btn_save)
        self.assertIsNotNone(app.btn_train)
        self.assertIsNotNone(app.btn_start)
        self.assertIsNotNone(app.filter_chips_row)

    def test_log_processing_and_filtering(self):
        page = MagicMock(spec=ft.Page)
        page.window = MagicMock()
        page.fonts = {}
        page.add = MagicMock()
        page.update = MagicMock()
        page.run_task = MagicMock()

        with patch('desktop_app.AlgoBotApp.fetch_balance'):
            app = desktop_app.AlgoBotApp(page)

        app.log_message('[GO] BUY BTC/USDT Entry: 65000')
        app.log_message('[V] ETH/USDT approved')
        app.log_message('[X] SOL/USDT (1-й слой: NO_TREND) rejected')
        app.log_message('[X] SOL/USDT (1-й слой: NO_TREND) rejected')
        app.log_message('[СИСТЕМА] RECOVERY active')
        app.log_message('[ОШИБКА] API Error')

        self.assertEqual(len(app.raw_logs), 5)
        self.assertEqual(app.raw_logs[2]['count'], 2)

        app._set_log_filter('SIGNALS')
        self.assertEqual(len(app.console_list.controls), 1)

        app._set_log_filter('REJECTS')
        self.assertEqual(len(app.console_list.controls), 1)

        app._set_log_filter('ALL')
        self.assertEqual(len(app.console_list.controls), 5)

    def test_position_rendering(self):
        page = MagicMock(spec=ft.Page)
        page.window = MagicMock()
        page.fonts = {}
        page.add = MagicMock()
        page.update = MagicMock()
        page.run_task = MagicMock()

        with patch('desktop_app.AlgoBotApp.fetch_balance'):
            app = desktop_app.AlgoBotApp(page)

        mock_positions = [
            {
                'symbol': 'BTC/USDT:USDT',
                'contracts': 0.05,
                'side': 'long',
                'entryPrice': 65000.0,
                'unrealizedPnl': 12.5,
                'info': {'leverage': 20, 'markPrice': 65250.0}
            }
        ]

        mock_fetcher = MagicMock()
        mock_fetcher.exchange.fetch_positions.return_value = mock_positions

        with patch('data_fetcher.DataFetcher', return_value=mock_fetcher):
            app._fetch_and_render_positions()

        self.assertEqual(len(app.positions_col.controls), 1)

if __name__ == '__main__':
    unittest.main()
