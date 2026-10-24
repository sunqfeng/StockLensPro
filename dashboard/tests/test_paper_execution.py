import unittest
from datetime import date

from stocklens.paper_trading import _price_limit_pct, limit_locked


class ExecutionLimitTests(unittest.TestCase):
    def test_main_board_st_rule_changes_on_effective_date(self):
        self.assertEqual(_price_limit_pct('000056', '*ST皇庭', date(2026, 7, 5)), 5)
        self.assertEqual(_price_limit_pct('000056', '*ST皇庭', date(2026, 7, 6)), 10)

    def test_growth_boards_override_st_name(self):
        for code, expected in [('300001', 20), ('688001', 20), ('920001', 30)]:
            with self.subTest(code=code):
                self.assertEqual(_price_limit_pct(code, '*ST测试', date(2026, 10, 23)), expected)

    def test_st_can_sell_at_minus_six_percent_in_current_rules(self):
        quote = {'stock_code': '000056', 'stock_name': '*ST皇庭',
                 'prev_close': 10, 'close_price': 9.4, 'quote_time': '2026-10-23 14:45:00'}
        self.assertFalse(limit_locked(quote, 'SELL'))
        quote['close_price'] = 9
        self.assertTrue(limit_locked(quote, 'SELL'))

    def test_limit_tick_uses_half_up_rounding(self):
        quote = {'stock_code': '000056', 'stock_name': '*ST皇庭',
                 'prev_close': 10.05, 'close_price': 11.05, 'quote_time': '2026-10-23 14:45:00'}
        self.assertFalse(limit_locked(quote, 'BUY'))
        quote['close_price'] = 11.06
        self.assertTrue(limit_locked(quote, 'BUY'))

    def test_nonfinite_and_undated_quotes_fail_closed(self):
        base = {'stock_code': '000001', 'prev_close': 10, 'close_price': 10,
                'quote_time': '2026-10-23 14:45:00'}
        for value in [float('nan'), float('inf'), 0, -1]:
            self.assertTrue(limit_locked(dict(base, close_price=value), 'BUY'))
        base.pop('quote_time')
        self.assertTrue(limit_locked(base, 'BUY'))


if __name__ == '__main__':
    unittest.main()
