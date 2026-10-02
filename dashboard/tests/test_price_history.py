import unittest
from datetime import datetime

import pandas as pd

from stocklens.data.price_history import build_price_history
from stocklens.pages.stock_price_history import make_price_chart


class PriceHistoryTests(unittest.TestCase):
    def test_extends_past_twenty_days_to_today_and_excludes_future(self):
        daily = pd.DataFrame({"trade_date": pd.bdate_range("2026-09-01", "2026-10-16"), "close_price": 12.0})
        frame = build_price_history(daily, "2026-09-01", 10, datetime(2026, 10, 15, 16))
        self.assertGreater(len(frame), 20)
        self.assertEqual(frame.iloc[-1]["trade_date"], pd.Timestamp("2026-10-15"))
        self.assertAlmostEqual(frame.iloc[-1]["return_pct"], 20)

    def test_current_quote_replaces_today_without_duplicate_date(self):
        daily = pd.DataFrame({"trade_date": ["2026-10-14", "2026-10-15"], "close_price": [10, 11]})
        frame = build_price_history(daily, "2026-10-14", 10, datetime(2026, 10, 15, 14),
                                    {"quote_time": "2026-10-15 13:59:00", "close_price": 12})
        self.assertEqual(len(frame), 2)
        self.assertEqual(frame.iloc[-1]["close_price"], 12)
        self.assertIn("盘中价格", frame.iloc[-1]["price_type"])

    def test_stale_quote_does_not_create_a_holiday_point(self):
        daily = pd.DataFrame({"trade_date": ["2026-09-30"], "close_price": [12]})
        frame = build_price_history(daily, "2026-09-30", 10, datetime(2026, 10, 2, 16),
                                    {"quote_time": "2026-09-30 15:00:00", "close_price": 99})
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.iloc[-1]["close_price"], 12)

    def test_actual_recommendation_day_close_is_preserved_and_reference_separate(self):
        daily = pd.DataFrame({"trade_date": ["2026-10-14"], "close_price": [11]})
        frame = build_price_history(daily, "2026-10-14", 10, datetime(2026, 10, 15, 16))
        fig = make_price_chart(frame, "2026-10-14", 10)
        self.assertEqual(fig.data[0].y[0], 11)
        self.assertEqual(fig.data[1].y[0], 10)

    def test_missing_recommendation_day_uses_labeled_start_and_rejects_invalid_prices(self):
        daily = pd.DataFrame({"trade_date": ["2026-10-15", "2026-10-16"], "close_price": [12, -1]})
        frame = build_price_history(daily, "2026-10-14", 10, datetime(2026, 10, 16, 16))
        self.assertEqual(len(frame), 2)
        self.assertEqual(frame.iloc[0]["price_type"], "推荐价起点")
        with self.assertRaises(ValueError):
            build_price_history(daily, "2026-10-14", 0, datetime(2026, 10, 16, 16))


if __name__ == "__main__":
    unittest.main()
