from behavior_recognition.temporal import BehaviorEventAggregator, FramePrediction


def _frame(timestamp: int, label: str, confidence: float = 0.9, quality: bool = True) -> FramePrediction:
    return FramePrediction(timestamp, label, confidence, quality)


def test_single_phone_frame_never_creates_event() -> None:
    aggregator = BehaviorEventAggregator(phone_enter_ms=2000, exit_ms=1000)

    assert aggregator.update(_frame(0, "PHONE_INTERACTION")) == []


def test_sustained_phone_frames_create_one_stable_event() -> None:
    aggregator = BehaviorEventAggregator(phone_enter_ms=2000, exit_ms=1000)

    aggregator.update(_frame(0, "PHONE_INTERACTION"))
    aggregator.update(_frame(1000, "PHONE_INTERACTION"))
    events = aggregator.update(_frame(2000, "PHONE_INTERACTION"))

    assert len(events) == 1
    assert events[0].label == "PHONE_INTERACTION"
    assert events[0].started_at_ms == 0
    assert events[0].active is True
    assert events[0].reminder_allowed is True


def test_uncertain_frame_neither_advances_nor_clears_phone_state() -> None:
    aggregator = BehaviorEventAggregator(phone_enter_ms=2000, exit_ms=1000)
    aggregator.update(_frame(0, "PHONE_INTERACTION"))
    aggregator.update(_frame(1000, "UNCERTAIN", quality=False))

    events = aggregator.update(_frame(2000, "PHONE_INTERACTION"))

    assert events[0].active is True


def test_exit_hysteresis_and_reminder_cooldown() -> None:
    aggregator = BehaviorEventAggregator(phone_enter_ms=2000, exit_ms=1000, reminder_cooldown_ms=600_000)
    aggregator.update(_frame(0, "PHONE_INTERACTION"))
    aggregator.update(_frame(2000, "PHONE_INTERACTION"))
    assert aggregator.update(_frame(2500, "STUDY_ACTIVITY")) == []
    ended = aggregator.update(_frame(3500, "STUDY_ACTIVITY"))
    assert ended[0].active is False
    aggregator.update(_frame(4000, "PHONE_INTERACTION"))
    restarted = aggregator.update(_frame(6000, "PHONE_INTERACTION"))
    assert restarted[0].active is True
    assert restarted[0].reminder_allowed is False


def test_reset_starts_a_new_cooldown_scope() -> None:
    aggregator = BehaviorEventAggregator(phone_enter_ms=1000, reminder_cooldown_ms=600_000)
    aggregator.update(_frame(0, "PHONE_INTERACTION"))
    assert aggregator.update(_frame(1000, "PHONE_INTERACTION"))[0].reminder_allowed is True
    aggregator.reset()
    aggregator.update(_frame(2000, "PHONE_INTERACTION"))

    assert aggregator.update(_frame(3000, "PHONE_INTERACTION"))[0].reminder_allowed is True
