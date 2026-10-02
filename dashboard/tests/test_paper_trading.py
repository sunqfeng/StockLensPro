import unittest
from datetime import datetime
from unittest.mock import patch

import pandas as pd

from stocklens.pages.paper_trading import _overview_summary
from stocklens.paper_trading import (
    DEFAULT_CONFIG,
    calculate_buy_quantity,
    exit_reason,
    is_a_share_trading_day,
    run_tick,
    validate_config,
)


class PaperTradingTests(unittest.TestCase):
    def test_overview_separates_total_realized_and_floating_pnl(self):
        account = {"initial_cash": 1_000.0, "cash": 400.0}
        positions = pd.DataFrame(
            [{"quantity": 10, "entry_price": 55.0, "entry_fee": 5.0, "current_price": 50.0}]
        )
        closed = pd.DataFrame([{"realized_pnl": -45.0}])
        nav = pd.DataFrame([{"drawdown_pct": -10.0, "total_fees": 12.0}])

        summary = _overview_summary(account, positions, closed, nav)

        self.assertEqual(summary["total_assets"], 900.0)
        self.assertEqual(summary["total_pnl"], -100.0)
        self.assertEqual(summary["realized"], -45.0)
        self.assertEqual(summary["unrealized"], -55.0)
        self.assertEqual(summary["wins"], 0)
        self.assertEqual(summary["losses"], 1)

    def test_money_and_exit_rules(self):
        config = validate_config(DEFAULT_CONFIG)
        quantity, price, fee = calculate_buy_quantity(100_000, 100_000, 10, config)
        self.assertEqual(quantity, 900)
        self.assertGreater(price, 10)
        self.assertEqual(fee, 5)
        self.assertEqual(exit_reason(11, 11, 9.5, 1, 20), "止盈")
        self.assertEqual(exit_reason(9.5, 11, 9.5, 1, 20), "止损")
        self.assertEqual(exit_reason(10, 11, 9.5, 20, 20), "到期")
        self.assertIsNone(exit_reason(10, 11, 9.5, 5, 20))

    def test_monitoring_runs_through_1530(self):
        with patch("stocklens.paper_trading.is_a_share_trading_day", return_value=True), \
             patch("stocklens.paper_trading.now_cn", return_value=datetime(2026, 9, 7, 15, 30)), \
             patch("stocklens.paper_trading.monitor_positions", return_value="checked"):
            self.assertEqual(run_tick(), "checked")
        with patch("stocklens.paper_trading.is_a_share_trading_day", return_value=True), \
             patch("stocklens.paper_trading.now_cn", return_value=datetime(2026, 9, 7, 15, 31)):
            self.assertEqual(run_tick(), "非交易时段。")

    def test_a_share_holiday_is_not_a_trading_day(self):
        with patch("stocklens.paper_trading._trade_dates", return_value={"2026-09-30"}):
            self.assertTrue(is_a_share_trading_day(datetime(2026, 9, 30).date()))
            self.assertFalse(is_a_share_trading_day(datetime(2026, 10, 1).date()))


if __name__ == "__main__":
    unittest.main()
