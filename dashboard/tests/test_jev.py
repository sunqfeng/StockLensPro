import unittest
from types import SimpleNamespace

from stocklens.integrations.jev import (
    QUESTION_VERSION,
    build_signal_state,
    evaluate_signal,
)


class _RawResponse:
    def json(self):
        return {"model": "jev-test", "answers": {"fixture": True}}


class _SuccessfulClient:
    def system_one(self, state, questions):
        self.state = state
        self.questions = questions
        return SimpleNamespace(
            model="jev-test",
            nouls={
                "signal_quality": SimpleNamespace(noul=0.81),
                "risk_conflict": SimpleNamespace(noul=0.19),
            },
            scores={
                "setup_quality": SimpleNamespace(score=2.4, confidence=0.72),
            },
            raw_http_response=_RawResponse(),
        )


class _FailingClient:
    def system_one(self, state, questions):
        raise RuntimeError("temporary failure")


class JevIntegrationTests(unittest.TestCase):
    def test_build_signal_state_keeps_the_input_small_and_structured(self):
        state = build_signal_state(
            stock_code="000001",
            stock_name="Example Bank",
            industry="Banking",
            strategy_code="TREND_PULLBACK_V2",
            strategy_name="Trend Pullback",
            recommend_score=82.5,
            reason="Trend and volume agree",
            quote={"close_price": 12.36, "prev_close": 12.0, "quote_time": "2026-09-22 14:10:00"},
            account={"cash": 380_000},
            config={"max_positions": 10, "max_daily_buys": 3, "position_pct": 10},
            open_positions=6,
        )

        self.assertEqual(state["stock"]["code"], "000001")
        self.assertEqual(state["market"]["daily_change_pct"], 3.0)
        self.assertEqual(state["account"]["open_positions"], 6)
        self.assertNotIn("api_key", str(state).lower())

    def test_evaluate_signal_returns_typed_shadow_metrics(self):
        client = _SuccessfulClient()

        result = evaluate_signal({"stock": {"code": "000001"}}, client=client)

        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["mode"], "SHADOW")
        self.assertEqual(result["question_version"], QUESTION_VERSION)
        self.assertEqual(result["model_resolved"], "jev-test")
        self.assertEqual(result["quality_probability"], 0.81)
        self.assertEqual(result["risk_probability"], 0.19)
        self.assertEqual(result["setup_score"], 2.4)
        self.assertEqual(result["setup_confidence"], 0.72)
        self.assertEqual(result["response_json"]["model"], "jev-test")

    def test_evaluate_signal_failure_is_recordable_and_does_not_raise(self):
        result = evaluate_signal({"stock": {"code": "000001"}}, client=_FailingClient())

        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["mode"], "SHADOW")
        self.assertIn("temporary failure", result["error_message"])
        self.assertIsNone(result["quality_probability"])


if __name__ == "__main__":
    unittest.main()
