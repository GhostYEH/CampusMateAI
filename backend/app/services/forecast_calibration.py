"""离线校准框架 — 计算预测校准指标。

指标：
- Brier Score
- ECE（Expected Calibration Error）
- coverage
- abstention rate
- schema validity
- evidence coverage
- stale-input rejection

如果没有真实标签，必须标记 synthetic 或 not_measured，
不能用合成结果冒充真实效果。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal

from ..schemas.forecast import (
    CalibrationMetricOut,
    CalibrationReportOut,
    ForecastOut,
)
from .forecast_service import FORECAST_ESTIMATOR_VERSION

LabelSource = Literal["real_outcomes", "synthetic", "not_measured"]


@dataclass(frozen=True)
class CalibrationSample:
    forecast: ForecastOut
    outcome: float | None  # 0.0 or 1.0, None if abstained


class ForecastCalibrationService:
    """离线校准框架。

    不修改在线预测，只计算指标。
    没有真实标签时标记 synthetic 或 not_measured。
    """

    @staticmethod
    def brier_score(samples: Iterable[CalibrationSample]) -> tuple[float, int, LabelSource]:
        scored = [s for s in samples if s.outcome is not None and s.forecast.probability is not None]
        if not scored:
            return 0.0, 0, "not_measured"
        total = sum((s.forecast.probability - s.outcome) ** 2 for s in scored)
        return total / len(scored), len(scored), "synthetic"

    @staticmethod
    def expected_calibration_error(
        samples: Iterable[CalibrationSample], *, bins: int = 10,
    ) -> tuple[float, int, LabelSource]:
        scored = [s for s in samples if s.outcome is not None and s.forecast.probability is not None]
        if not scored:
            return 0.0, 0, "not_measured"
        bin_edges = [i / bins for i in range(bins + 1)]
        ece = 0.0
        total = len(scored)
        for i in range(bins):
            lo, hi = bin_edges[i], bin_edges[i + 1]
            bucket = [s for s in scored if lo <= s.forecast.probability < hi or (i == bins - 1 and s.forecast.probability == hi)]
            if not bucket:
                continue
            avg_conf = sum(s.forecast.probability for s in bucket) / len(bucket)
            avg_acc = sum(s.outcome for s in bucket) / len(bucket)
            ece += (len(bucket) / total) * abs(avg_acc - avg_conf)
        return ece, total, "synthetic"

    @staticmethod
    def coverage(samples: Iterable[CalibrationSample]) -> tuple[float, int, LabelSource]:
        sample_list = list(samples)
        if not sample_list:
            return 0.0, 0, "not_measured"
        covered = sum(1 for s in sample_list if s.forecast.data_quality != "unavailable")
        return covered / len(sample_list), len(sample_list), "not_measured"

    @staticmethod
    def abstention_rate(samples: Iterable[CalibrationSample]) -> tuple[float, int, LabelSource]:
        sample_list = list(samples)
        if not sample_list:
            return 0.0, 0, "not_measured"
        abstained = sum(1 for s in sample_list if s.forecast.data_quality == "unavailable")
        return abstained / len(sample_list), len(sample_list), "not_measured"

    @staticmethod
    def schema_validity(samples: Iterable[CalibrationSample]) -> tuple[float, int, LabelSource]:
        sample_list = list(samples)
        if not sample_list:
            return 0.0, 0, "not_measured"
        valid = 0
        for s in sample_list:
            f = s.forecast
            try:
                if 0 <= f.confidence <= 1 and f.horizon_end > f.horizon_start:
                    if f.data_quality == "unavailable":
                        if f.probability is None and f.confidence == 0:
                            valid += 1
                    else:
                        if f.probability is not None and 0 <= f.probability <= 1:
                            valid += 1
            except Exception:
                pass
        return valid / len(sample_list), len(sample_list), "not_measured"

    @staticmethod
    def evidence_coverage(samples: Iterable[CalibrationSample]) -> tuple[float, int, LabelSource]:
        sample_list = list(samples)
        if not sample_list:
            return 0.0, 0, "not_measured"
        covered = 0
        for s in sample_list:
            ev = s.forecast.evidence_summary
            total_evidence = (
                ev.observed_session_count + ev.observed_task_count
                + ev.observed_goal_count + ev.observed_schedule_count
                + ev.observed_exam_count
            )
            if total_evidence > 0 or s.forecast.data_quality == "unavailable":
                covered += 1
        return covered / len(sample_list), len(sample_list), "not_measured"

    @staticmethod
    def stale_input_rejection(samples: Iterable[CalibrationSample], *, as_of: datetime) -> tuple[float, int, LabelSource]:
        sample_list = list(samples)
        if not sample_list:
            return 0.0, 0, "not_measured"
        rejected = 0
        for s in sample_list:
            valid_until = s.forecast.valid_until
            if valid_until.tzinfo is None:
                valid_until = valid_until.replace(tzinfo=timezone.utc)
            if as_of >= valid_until and s.forecast.data_quality == "stale":
                rejected += 1
        return rejected / len(sample_list), len(sample_list), "not_measured"

    def evaluate(
        self,
        *,
        samples: Iterable[CalibrationSample],
        as_of: datetime,
        forecast_type: str | None = None,
    ) -> CalibrationReportOut:
        sample_list = list(samples)
        metrics: list[CalibrationMetricOut] = []
        brier, n_brier, ls_brier = self.brier_score(sample_list)
        metrics.append(CalibrationMetricOut(
            metric_name="brier_score", value=brier, sample_size=n_brier,
            label_source=ls_brier, note="lower is better",
        ))
        ece, n_ece, ls_ece = self.expected_calibration_error(sample_list)
        metrics.append(CalibrationMetricOut(
            metric_name="expected_calibration_error", value=ece, sample_size=n_ece,
            label_source=ls_ece, note="lower is better",
        ))
        cov, n_cov, ls_cov = self.coverage(sample_list)
        metrics.append(CalibrationMetricOut(
            metric_name="coverage", value=cov, sample_size=n_cov,
            label_source=ls_cov, note="fraction of non-abstained forecasts",
        ))
        abst, n_abst, ls_abst = self.abstention_rate(sample_list)
        metrics.append(CalibrationMetricOut(
            metric_name="abstention_rate", value=abst, sample_size=n_abst,
            label_source=ls_abst, note="fraction of UNAVAILABLE forecasts",
        ))
        sv, n_sv, ls_sv = self.schema_validity(sample_list)
        metrics.append(CalibrationMetricOut(
            metric_name="schema_validity", value=sv, sample_size=n_sv,
            label_source=ls_sv, note="fraction of schema-valid forecasts",
        ))
        ec, n_ec, ls_ec = self.evidence_coverage(sample_list)
        metrics.append(CalibrationMetricOut(
            metric_name="evidence_coverage", value=ec, sample_size=n_ec,
            label_source=ls_ec, note="fraction with non-empty evidence",
        ))
        sir, n_sir, ls_sir = self.stale_input_rejection(sample_list, as_of=as_of)
        metrics.append(CalibrationMetricOut(
            metric_name="stale_input_rejection", value=sir, sample_size=n_sir,
            label_source=ls_sir, note="fraction of stale inputs rejected",
        ))
        if any(m.label_source == "real_outcomes" for m in metrics):
            overall: LabelSource = "real_outcomes"
        elif any(m.label_source == "synthetic" for m in metrics):
            overall = "synthetic"
        else:
            overall = "not_measured"
        return CalibrationReportOut(
            estimator_version=FORECAST_ESTIMATOR_VERSION,
            forecast_type=forecast_type,
            as_of=as_of,
            metrics=metrics,
            overall_label_source=overall,
        )


__all__ = ["ForecastCalibrationService", "CalibrationSample"]