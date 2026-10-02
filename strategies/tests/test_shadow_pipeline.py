import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from shadow_pipeline import run_shadow


class PipelineTests(unittest.TestCase):
    def test_readonly_snapshot_is_immutable_and_has_version_and_inputs(self):
        row=dict(id=1,stock_code="001326",strategy_name="均线金叉放量",
                 recommend_date=date(2026,9,30),daily_date=date(2026,9,30),
                 close_price=10,recommend_price=10,data_quality="HIGH")
        market=pd.DataFrame([dict(breadth=50,coverage=1)])
        engine=object()
        with tempfile.TemporaryDirectory() as folder:
            with patch("shadow_pipeline.pd.read_sql",side_effect=[market,pd.DataFrame([row])]):
                target=run_shadow(engine,"2026-09-30","../../batch",Path(folder))
            original=target.read_text(encoding="utf-8")
            payload=json.loads(original)
            self.assertEqual(payload['mode'],"历史/盘中重放")
            self.assertEqual(payload['records'][0]['decision'],"候选保留")
            self.assertEqual(payload['records'][0]['close_price'],10)
            self.assertEqual(target.parent,Path(folder))
            with patch("shadow_pipeline.pd.read_sql") as sql:
                self.assertEqual(run_shadow(engine,"2026-09-30","../../batch",Path(folder)),target)
                sql.assert_not_called()
            self.assertEqual(target.read_text(encoding="utf-8"),original)

    def test_future_date_rejected_without_querying(self):
        with patch("shadow_pipeline.pd.read_sql") as sql:
            with self.assertRaises(ValueError):
                run_shadow(object(),"2099-01-01","x")
            sql.assert_not_called()


if __name__ == "__main__":
    unittest.main()
