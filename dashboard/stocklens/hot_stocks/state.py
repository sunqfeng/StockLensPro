from dataclasses import dataclass
from enum import StrEnum


class TrackingStatus(StrEnum):
    TOP50 = "TOP50"
    OBSERVING = "OBSERVING"
    OUTSIDE_TOP100 = "OUTSIDE_TOP100"
    HISTORY = "HISTORY"
    PINNED = "PINNED"


class EventType(StrEnum):
    FIRST_ENTER_TOP50 = "FIRST_ENTER_TOP50"
    EXIT_TOP50 = "EXIT_TOP50"
    REENTER_TOP50 = "REENTER_TOP50"
    EXIT_TOP100 = "EXIT_TOP100"
    TRACKING_EXPIRED = "TRACKING_EXPIRED"


@dataclass(frozen=True)
class TransitionResult:
    status: TrackingStatus | None
    current_rank: int | None
    events: tuple[EventType, ...]


def decide_transition(
    *,
    previous_status: TrackingStatus | None,
    previous_rank: int | None,
    current_rank: int | None,
    has_entered_top50: bool,
    successful_batch: bool,
    primary_cutoff: int = 50,
    observation_cutoff: int = 100,
) -> TransitionResult:
    """根据两个相邻成功批次判断当前跟踪状态和生命周期事件。"""
    if not successful_batch:
        return TransitionResult(previous_status, previous_rank, ())

    if primary_cutoff < 1 or observation_cutoff <= primary_cutoff:
        raise ValueError("排名边界配置无效")
    if current_rank is not None and not 1 <= current_rank <= observation_cutoff:
        raise ValueError("当前排名必须位于已采集范围内")

    if current_rank is None:
        events = []
        if previous_status == TrackingStatus.TOP50:
            events.append(EventType.EXIT_TOP50)
        if previous_status != TrackingStatus.OUTSIDE_TOP100:
            events.append(EventType.EXIT_TOP100)
        return TransitionResult(
            TrackingStatus.OUTSIDE_TOP100,
            None,
            tuple(events),
        )

    if current_rank <= primary_cutoff:
        events = []
        if previous_status != TrackingStatus.TOP50:
            events.append(
                EventType.REENTER_TOP50
                if has_entered_top50
                else EventType.FIRST_ENTER_TOP50
            )
        return TransitionResult(TrackingStatus.TOP50, current_rank, tuple(events))

    events = (
        (EventType.EXIT_TOP50,)
        if previous_status == TrackingStatus.TOP50
        else ()
    )
    return TransitionResult(TrackingStatus.OBSERVING, current_rank, events)
