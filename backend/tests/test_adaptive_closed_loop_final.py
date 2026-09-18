from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.adaptive_agent.replan_policy import ReplanDecision
from app.services.adaptive_agent.replanning_worker import AdaptiveReplanningWorker
from app.services.adaptive_agent.state_outcome_comparator import StateOutcomeComparator
from app.services.learner_event_service import LearnerEventService


def _decision(status="PENDING", decision="CONTINUE"):
    return SimpleNamespace(
        decision_id="rdec_1", status=status, decision=decision,
        reason_codes_json='["test"]', suggested_adjustments_json="[]",
    )


class _Evaluation:
    evaluation_id = "eval_1"
    adoption = "COMPLETED"
    observed_outcome = "IMPROVED"

    def model_dump(self, mode="json"):
        return {
            "evaluation_id": self.evaluation_id,
            "observed_outcome": "IMPROVED", "adoption": "COMPLETED",
            "state_comparison": {"after_values": {"stress_risk": 0.2}},
        }


class _Repo:
    def __init__(self, decision):
        self.decision = decision
        self.statuses = []

    def list_due_for_evaluation(self, **kwargs):
        return []

    def list_pending_decisions(self, **kwargs):
        return [(SimpleNamespace(user_id="u1", goal_id="g1", intervention_id="i1"), self.decision)]

    def get_evaluation(self, **kwargs):
        return object()

    def update_decision_status(self, **kwargs):
        self.statuses.append(kwargs)
        self.decision.status = kwargs["status"]
        return self.decision


class _Events:
    def __init__(self, failures=1):
        self.failures = failures
        self.calls = []

    def record_intervention_event(self, **kwargs):
        self.calls.append(kwargs)
        if self.failures:
            self.failures -= 1
            raise RuntimeError("temporary event store outage")


class _Service:
    def __init__(self, events):
        self._learner_event_service = events

    def _restore_evaluation(self, row):
        return _Evaluation()

    def _load_goal(self, **kwargs):
        return None

    def replan_from_evaluation(self, **kwargs):
        return SimpleNamespace(intervention=SimpleNamespace(intervention_id="successor_1"))


class _RetryRepo(_Repo):
    def __init__(self, decision):
        super().__init__(decision)
        self.next_retry_at = None
        self.retry_count = 0

    def list_pending_decisions(self, *, as_of, **kwargs):
        if self.next_retry_at is not None and as_of < self.next_retry_at:
            return []
        return super().list_pending_decisions(**kwargs)

    def mark_decision_failure(self, *, decision_id, failure_code, retryable, now, **kwargs):
        self.retry_count += 1
        if retryable and self.retry_count <= 3:
            self.next_retry_at = (now + timedelta(seconds=60)).isoformat()
        self.decision.status = "FAILED"


def test_comparator_confidence_is_bounded_by_quality_and_provenance():
    comparator = StateOutcomeComparator()
    result = comparator.compare(
        before={"mastery": 0.4, "_dimensions": {"mastery": {"data_quality": "partial", "confidence": 0.5}}},
        after={"mastery": 0.6, "_dimensions": {"mastery": {"data_quality": "partial", "confidence": 0.5}}},
        strategy_code="FOUNDATION_REINFORCEMENT", comparison_as_of="2026-09-18T00:00:00+00:00",
        evidence_refs=[],
    )
    assert result["confidence"] < 0.7


def test_challenge_upshift_uses_mastery_and_goal_gap():
    result = StateOutcomeComparator().compare(
        before={"mastery": 0.4, "goal_gap": 0.8},
        after={"mastery": 0.6, "goal_gap": 0.5},
        strategy_code="CHALLENGE_UPSHIFT", comparison_as_of="2026-09-18T00:00:00+00:00",
    )
    assert result["outcome"] == "IMPROVED"
    assert result["relevant_dimensions"] == ["mastery", "goal_gap"]


def test_unknown_strategy_does_not_fall_back_to_pace_dimensions():
    result = StateOutcomeComparator().compare(
        before={"consistency": 0.2, "completion_rate": 0.2},
        after={"consistency": 0.9, "completion_rate": 0.9},
        strategy_code="UNKNOWN_STRATEGY", comparison_as_of="2026-09-18T00:00:00+00:00",
    )
    assert result["outcome"] == "INSUFFICIENT_EVIDENCE"
    assert result["warnings"] == ["unknown_strategy_code"]


def test_after_provenance_is_the_conservative_confidence_bound():
    complete = {
        "before_data_quality": "verified", "after_data_quality": "verified",
        "before_confidence": 1.0, "after_confidence": 1.0,
        "before_snapshot_id": "b-snap", "after_snapshot_id": "a-snap",
        "before_run_id": "b-run", "after_run_id": "a-run",
        "before_observed_at": "2026-09-18T00:00:00+00:00", "after_observed_at": "2026-09-18T00:00:00+00:00",
        "before_valid_until": "2026-09-19T00:00:00+00:00", "after_valid_until": "2026-09-19T00:00:00+00:00",
        "evidence_refs": ["b-snap", "a-snap"],
    }
    degraded = {**complete, "after_data_quality": "partial", "after_confidence": 0.2,
                "after_valid_until": "2026-09-17T00:00:00+00:00"}
    good = StateOutcomeComparator().compare(
        before={"mastery": 0.4, "_dimensions": {"mastery": complete}},
        after={"mastery": 0.6, "_dimensions": {"mastery": complete}},
        strategy_code="FOUNDATION_REINFORCEMENT", comparison_as_of="2026-09-18T00:00:00+00:00",
    )
    limited = StateOutcomeComparator().compare(
        before={"mastery": 0.4, "_dimensions": {"mastery": degraded}},
        after={"mastery": 0.6, "_dimensions": {"mastery": degraded}},
        strategy_code="FOUNDATION_REINFORCEMENT", comparison_as_of="2026-09-18T00:00:00+00:00",
    )
    assert limited["confidence"] < good["confidence"]


def test_event_failure_keeps_decision_recoverable_then_applies():
    decision = _decision()
    repo = _Repo(decision)
    events = _Events(failures=1)
    worker = AdaptiveReplanningWorker(
        repository=repo, intervention_service=_Service(events),
        clock=lambda: datetime(2026, 9, 18, tzinfo=timezone.utc),
    )
    first = worker.tick()
    assert first.failed == 1
    assert decision.status != "APPLIED"
    second = worker.tick()
    assert second.applied == 1
    assert decision.status == "APPLIED"
    assert len(events.calls) >= 2


def test_replan_failure_is_retryable_and_does_not_duplicate_successor():
    decision = _decision(decision="REPLAN")
    repo = _RetryRepo(decision)
    events = _Events(failures=0)
    service = _Service(events)
    calls = []

    def replan(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("temporary planner unavailable")
        return SimpleNamespace(intervention=SimpleNamespace(intervention_id="successor_1"))

    service.replan_from_evaluation = replan
    current = [datetime(2026, 9, 18, tzinfo=timezone.utc)]
    worker = AdaptiveReplanningWorker(
        repository=repo, intervention_service=service,
        clock=lambda: current[0],
    )
    worker.tick()
    assert decision.status != "APPLIED"
    assert repo.retry_count == 1
    assert worker.tick().scanned == 0
    current[0] += timedelta(seconds=60)
    report = worker.tick()
    assert report.applied == 1
    assert len(calls) == 2


def test_observed_event_carries_real_adoption_and_outcome():
    class Repo:
        def append_idempotent(self, *, user_id, event):
            self.event = event
            return SimpleNamespace(event_id="evt_1", created=True)

    repo = Repo()
    LearnerEventService(repo).record_intervention_event(
        user_id="u1", event_type="intervention_observed", intervention_id="i1", goal_id="g1",
        occurred_at=datetime(2026, 9, 18, tzinfo=timezone.utc), adoption="COMPLETED",
        observed_outcome="INSUFFICIENT_EVIDENCE", evaluation_id="eval_1",
        outcome="observed_completed",
    )
    assert repo.event.payload["adoption"] == "COMPLETED"
    assert repo.event.payload["observed_outcome"] == "INSUFFICIENT_EVIDENCE"
