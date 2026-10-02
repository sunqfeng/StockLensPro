import json
import unittest
from decimal import Decimal

from stocklens.hot_stocks.collector import (
    HotStockValidationError,
    parse_hot_stock_html,
)


def build_html(items):
    store = {
        "page": {
            "nested": {
                "items": items,
                "loaded": True,
            }
        }
    }
    payload = json.dumps(store, ensure_ascii=False)
    return f'<html><script id="initStore">window.__INITIAL_STORE__={payload}</script></html>'


class ParseHotStockHtmlTests(unittest.TestCase):
    def test_parses_and_normalizes_multi_market_records(self):
        html = build_html(
            [
                {
                    "symbol": "SH603259",
                    "name": "药明康德",
                    "value": 2915,
                    "percent": 8.49,
                    "exchange": "SH",
                    "hot": {"tag": "#创新药持续活跃#"},
                },
                {
                    "symbol": "00700",
                    "name": "腾讯控股",
                    "value": 880,
                    "percent": -0.08,
                    "exchange": "HK",
                },
                {
                    "symbol": "NVDA",
                    "name": "英伟达",
                    "value": 351,
                    "percent": 2.2695,
                    "exchange": "NASDAQ",
                },
            ]
        )

        records = parse_hot_stock_html(html, limit=100)

        self.assertEqual([record.rank_no for record in records], [1, 2, 3])
        self.assertEqual(records[0].normalized_code, "603259")
        self.assertEqual(records[0].market, "CN_SH")
        self.assertEqual(records[0].heat_score, Decimal("2915"))
        self.assertEqual(records[0].quote_change_pct, Decimal("8.49"))
        self.assertEqual(records[0].topic, "#创新药持续活跃#")
        self.assertIsNone(records[1].normalized_code)
        self.assertEqual(records[1].market, "HK")
        self.assertEqual(records[2].market, "US")

    def test_limit_is_applied_after_validation(self):
        html = build_html(
            [
                {"symbol": "SH600001", "name": "股票一", "value": 20, "exchange": "SH"},
                {"symbol": "SZ000002", "name": "股票二", "value": 10, "exchange": "SZ"},
            ]
        )

        records = parse_hot_stock_html(html, limit=1)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].external_symbol, "SH600001")

    def test_missing_initial_store_is_rejected(self):
        with self.assertRaisesRegex(HotStockValidationError, "初始状态"):
            parse_hot_stock_html("<html><body>no data</body></html>")

    def test_duplicate_symbols_are_rejected(self):
        html = build_html(
            [
                {"symbol": "SH600001", "name": "股票一", "value": 20, "exchange": "SH"},
                {"symbol": "SH600001", "name": "股票一", "value": 19, "exchange": "SH"},
            ]
        )

        with self.assertRaisesRegex(HotStockValidationError, "重复"):
            parse_hot_stock_html(html)

    def test_javascript_undefined_values_are_treated_as_null(self):
        html = build_html(
            [{"symbol": "SH600001", "name": "股票一", "value": 20, "exchange": "SH"}]
        ).replace('"loaded": true', '"loaded": true, "isLogin": undefined')

        records = parse_hot_stock_html(html)

        self.assertEqual(records[0].external_symbol, "SH600001")

    def test_invalid_limit_is_rejected(self):
        html = build_html(
            [{"symbol": "SH600001", "name": "股票一", "value": 20, "exchange": "SH"}]
        )

        with self.assertRaises(ValueError):
            parse_hot_stock_html(html, limit=0)


if __name__ == "__main__":
    unittest.main()
