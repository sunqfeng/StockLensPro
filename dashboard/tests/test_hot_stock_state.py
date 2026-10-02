import unittest

from stocklens.hot_stocks.state import (
    EventType,
    TrackingStatus,
    decide_transition,
)


class DecideTransitionTests(unittest.TestCase):
    def test_failed_batch_never_changes_existing_state(self):
        result = decide_transition(
            previous_status=TrackingStatus.TOP50,
            previous_rank=18,
            current_rank=None,
            has_entered_top50=True,
            successful_batch=False,
        )

        self.assertEqual(result.status, TrackingStatus.TOP50)
        self.assertEqual(result.current_rank, 18)
        self.assertEqual(result.events, ())

    def test_stock_falling_to_observation_range_exits_top50(self):
        result = decide_transition(
            previous_status=TrackingStatus.TOP50,
            previous_rank=47,
            current_rank=61,
            has_entered_top50=True,
            successful_batch=True,
        )

        self.assertEqual(result.status, TrackingStatus.OBSERVING)
        self.assertEqual(result.current_rank, 61)
        self.assertEqual(result.events, (EventType.EXIT_TOP50,))

    def test_stock_missing_from_top100_records_both_exit_events(self):
        result = decide_transition(
            previous_status=TrackingStatus.TOP50,
            previous_rank=47,
            current_rank=None,
            has_entered_top50=True,
            successful_batch=True,
        )

        self.assertEqual(result.status, TrackingStatus.OUTSIDE_TOP100)
        self.assertIsNone(result.current_rank)
        self.assertEqual(
            result.events,
            (EventType.EXIT_TOP50, EventType.EXIT_TOP100),
        )

    def test_observed_stock_reentering_top50_is_marked_as_reentry(self):
        result = decide_transition(
            previous_status=TrackingStatus.OBSERVING,
            previous_rank=63,
            current_rank=32,
            has_entered_top50=True,
            successful_batch=True,
        )

        self.assertEqual(result.status, TrackingStatus.TOP50)
        self.assertEqual(result.events, (EventType.REENTER_TOP50,))

    def test_first_top50_appearance_is_not_marked_as_reentry(self):
        result = decide_transition(
            previous_status=None,
            previous_rank=None,
            current_rank=14,
            has_entered_top50=False,
            successful_batch=True,
        )

        self.assertEqual(result.status, TrackingStatus.TOP50)
        self.assertEqual(result.events, (EventType.FIRST_ENTER_TOP50,))

    def test_first_appearance_below_top50_starts_observation_without_event(self):
        result = decide_transition(
            previous_status=None,
            previous_rank=None,
            current_rank=70,
            has_entered_top50=False,
            successful_batch=True,
        )

        self.assertEqual(result.status, TrackingStatus.OBSERVING)
        self.assertEqual(result.events, ())

    def test_rank_outside_collected_range_is_rejected(self):
        with self.assertRaises(ValueError):
            decide_transition(
                previous_status=None,
                previous_rank=None,
                current_rank=101,
                has_entered_top50=False,
                successful_batch=True,
            )


if __name__ == "__main__":
    unittest.main()
