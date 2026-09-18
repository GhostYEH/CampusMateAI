from datetime import datetime, timezone

from app.services.adaptive_agent.replanning_worker import AdaptiveReplanningWorker


class _Repo:
    def __init__(self): self.calls = []
    def list_due_for_evaluation(self, **kwargs): self.calls.append(kwargs); return []


def test_tick_is_direct_clock_injected_and_bounded() -> None:
    repo = _Repo()
    worker = AdaptiveReplanningWorker(
        repository=repo, intervention_service=object(),
        clock=lambda: datetime(2026, 9, 18, tzinfo=timezone.utc),
    )
    assert worker.tick(batch_size=3).scanned == 0
    assert repo.calls == [{"as_of": "2026-09-18T00:00:00+00:00", "limit": 3}]
