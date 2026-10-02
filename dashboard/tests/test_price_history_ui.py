import hashlib
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest


DATA = pd.DataFrame([
    {"推荐批次号": "20260909_001", "推荐日期": "2026-09-09", "推荐策略": "RPS强势突破",
     "股票代码": "001326", "股票名称": "联域股份", "推荐价格": 74.31},
    {"推荐批次号": "20260910_001", "推荐日期": "2026-09-10", "推荐策略": "RPS强势突破",
     "股票代码": "001326", "股票名称": "联域股份", "推荐价格": 73.66},
])


class PriceHistoryUITests(unittest.TestCase):
    def test_selecting_different_recommendations_changes_the_reference_and_chart(self):
        app = AppTest.from_string('''
import pandas as pd
from stocklens.pages.stock_price_history import render_stock_history_table
render_stock_history_table(pd.DataFrame([
    {"推荐批次号":"20260909_001", "推荐日期":"2026-09-09", "推荐策略":"RPS强势突破",
     "股票代码":"001326", "股票名称":"联域股份", "推荐价格":74.31,
     "所属行业":"LED", "推荐分数":90.63},
    {"推荐批次号":"20260910_001", "推荐日期":"2026-09-10", "推荐策略":"RPS强势突破",
     "股票代码":"001326", "股票名称":"联域股份", "推荐价格":73.66,
     "所属行业":None, "推荐分数":None},
]))
''')
        history = pd.DataFrame({
            "trade_date": pd.to_datetime(["2026-09-10", "2026-09-30"]),
            "close_price": [73.66, 101.03], "return_pct": [0.0, 37.16],
            "price_type": ["收盘价", "收盘价"],
        })
        with patch("stocklens.pages.stock_price_history.load_price_history", return_value=(history, None)) as loader:
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.get("plotly_chart")), 0)
            identities = DATA[["推荐批次号", "推荐日期", "推荐策略", "股票代码"]].astype(str)
            key = "stock_history_" + hashlib.sha256(identities.to_csv(index=False).encode()).hexdigest()[:16]
            for position, expected in [(0, "¥74.31"), (1, "¥73.66")]:
                app.session_state[key] = {"selection": {"rows": [position], "columns": [], "cells": []}}
                app.run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(app.metric[0].value, expected)
                self.assertEqual(len(app.get("plotly_chart")), 1)
                dialogs = app.get("dialog")
                self.assertEqual(len(dialogs), 1)
                self.assertEqual(len(dialogs[0].get("plotly_chart")), 1)
                heading = app.subheader[0].value
                if position == 0:
                    self.assertIn("板块：LED", heading)
                    self.assertIn("推荐时评分：90.63 分", heading)
                else:
                    self.assertIn("板块：未分类", heading)
                    self.assertIn("推荐时评分：暂无", heading)
                self.assertEqual(loader.call_args.args[1], DATA.iloc[position]["推荐日期"])


if __name__ == "__main__":
    unittest.main()
