import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import run_select_and_record as runner


class ShadowHookTests(unittest.TestCase):
    def test_shadow_failure_does_not_filter_or_break_saved_recommendations(self):
        records=[object(),object()]
        strategy=Mock(strategy_code="TEST",strategy_name="test")
        strategy.return_value.run.return_value=records
        repository=Mock()
        engine=Mock()
        args=SimpleNamespace(trade_date="2026-09-30",batch_no="20260930_001",strategy=None)
        with patch.object(runner,"parse_args",return_value=args), \
             patch.object(runner,"MySqlDataEngine",return_value=engine), \
             patch.object(runner,"STRATEGY_CLASSES",[strategy]), \
             patch.object(runner,"RecommendRecordRepository",return_value=repository), \
             patch.object(runner,"run_tech_score") as score, \
             patch("shadow_pipeline.run_shadow",side_effect=RuntimeError("unavailable")) as shadow:
            runner.main()
        repository.save_results.assert_called_once_with(records)
        score.assert_called_once_with("2026-09-30","20260930_001")
        shadow.assert_called_once_with(engine.engine,"2026-09-30","20260930_001")


if __name__ == "__main__":
    unittest.main()
