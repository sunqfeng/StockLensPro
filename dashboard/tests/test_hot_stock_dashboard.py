import unittest

import pandas as pd

from stocklens.data.hot_stock_loaders import (
    build_latest_comparison,
    select_heat_change_top,
)


class HotStockDashboardDataTests(unittest.TestCase):
    def test_change_chart_selects_largest_movers_by_absolute_percent(self):
        data = pd.DataFrame(
            [
                {"stock_name": "恒瑞医药", "heat_change_pct": 8.17},
                {"stock_name": "华正新材", "heat_change_pct": -12.22},
                {"stock_name": "有研新材", "heat_change_pct": 7.06},
                {"stock_name": "新上榜", "heat_change_pct": None},
            ]
        )

        result = select_heat_change_top(data, limit=2)

        self.assertEqual(
            result["stock_name"].tolist(),
            ["华正新材", "恒瑞医药"],
        )

    def test_latest_comparison_calculates_rank_and_heat_change_percent(self):
        latest = pd.DataFrame(
            [
                {"rank_no": 1, "external_symbol": "SH600001", "heat_score": 100},
                {"rank_no": 2, "external_symbol": "SH600002", "heat_score": 80},
                {"rank_no": 3, "external_symbol": "SH600003", "heat_score": 70},
            ]
        )
        previous = pd.DataFrame(
            [
                {"rank_no": 3, "external_symbol": "SH600001", "heat_score": 60},
                {"rank_no": 1, "external_symbol": "SH600002", "heat_score": 100},
            ]
        )

        result = build_latest_comparison(latest, previous).set_index("external_symbol")

        self.assertEqual(result.loc["SH600001", "rank_change"], 2)
        self.assertAlmostEqual(
            result.loc["SH600001", "heat_change_pct"],
            66.6667,
            places=4,
        )
        self.assertEqual(result.loc["SH600001", "change_direction"], "上升")
        self.assertEqual(result.loc["SH600002", "rank_change"], -1)
        self.assertEqual(result.loc["SH600002", "change_direction"], "下降")
        self.assertEqual(result.loc["SH600003", "change_direction"], "新上榜")

    def test_heat_change_percent_is_empty_when_previous_heat_is_zero(self):
        latest = pd.DataFrame(
            [{"rank_no": 1, "external_symbol": "SH600001", "heat_score": 100}]
        )
        previous = pd.DataFrame(
            [{"rank_no": 1, "external_symbol": "SH600001", "heat_score": 0}]
        )

        result = build_latest_comparison(latest, previous)

        self.assertTrue(pd.isna(result.loc[0, "heat_change_pct"]))

    def test_latest_comparison_keeps_only_top_50_in_rank_order(self):
        latest = pd.DataFrame(
            [
                {"rank_no": 51, "external_symbol": "SH600051", "heat_score": 20},
                {"rank_no": 2, "external_symbol": "SH600002", "heat_score": 80},
                {"rank_no": 1, "external_symbol": "SH600001", "heat_score": 100},
            ]
        )

        result = build_latest_comparison(latest, pd.DataFrame())

        self.assertEqual(result["rank_no"].tolist(), [1, 2])

    def test_latest_comparison_adds_latest_price_and_sector(self):
        latest = pd.DataFrame(
            [
                {
                    "rank_no": 1,
                    "external_symbol": "SH600001",
                    "normalized_code": "600001",
                    "heat_score": 100,
                }
            ]
        )
        market_data = pd.DataFrame(
            [
                {
                    "normalized_code": "600001",
                    "latest_price": 12.34,
                    "price_trade_date": "2026-08-07",
                    "sector_name": "化学制药",
                }
            ]
        )

        result = build_latest_comparison(
            latest,
            pd.DataFrame(),
            market_data=market_data,
        )

        self.assertEqual(result.loc[0, "latest_price"], 12.34)
        self.assertEqual(result.loc[0, "sector_name"], "化学制药")
        self.assertEqual(result.loc[0, "price_trade_date"], "2026-08-07")


if __name__ == "__main__":
    unittest.main()
