from datetime import datetime, timezone

from app.services.adaptive_agent.observation_window import ObservationWindowPolicy


def test_observation_due_at_is_independent_from_plan_freshness() -> None:
    now = datetime(2026, 9, 18, 2, 0, tzinfo=timezone.utc)
    due = ObservationWindowPolicy().due_at(
        planned_end="2026-09-20T12:00:00+00:00",
        generated_at=now,
    )
    assert due.isoformat() == "2026-09-21T12:00:00+00:00"
    assert due.isoformat() != "2026-09-18T02:15:00+00:00"


def test_observation_window_defaults_to_configured_days_without_a_task_due_date() -> None:
    now = datetime(2026, 9, 18, 2, 0, tzinfo=timezone.utc)
    assert ObservationWindowPolicy().due_at(planned_end=None, generated_at=now).isoformat() == "2026-09-25T02:00:00+00:00"
