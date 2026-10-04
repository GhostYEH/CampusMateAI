import { formatRelativeTime } from "../utils/date.js";
import '../styles/learning-state.css';
import { Link } from 'react-router-dom';
import { useLearningState } from '../hooks/useLearningState.js';
import { ErrorBar, QualityBadge } from '../components/learningState/shared.jsx';
import { StateOverview, WorldSnapshotSection, StateTimeline, ForecastSection } from '../components/learningState/StateOverview.jsx';
import { InterventionLoopSummary } from '../components/learningState/InterventionLoopSummary.jsx';
import { GoalsSection } from '../components/learningState/GoalsSection.jsx';
import { EvidenceDrawer } from '../components/learningState/EvidenceDrawer.jsx';
import { LearningPlanCenter, PlanEvaluationSection } from '../components/learningState/LearningPlanCenter.jsx';
import { GoalExecutionCenter } from '../components/learningState/GoalExecutionCenter.jsx';
import { DataPrivacyControl } from '../components/learningState/DataPrivacyControl.jsx';
import { ModelTransparency } from '../components/learningState/ModelTransparency.jsx';

/** Compose the learning overview, goals, plans and privacy controls. */
export default function LearningStatePage() {
  const {
    evidenceSnapshot,
    setEvidenceSnapshot,
    toast,
    busy,
    snapshots,
    worldSnapshots,
    changes,
    forecasts,
    goals,
    plans,
    currentIntervention,
    interventionOutcome,
    runtimeJobs,
    planSummary,
    controls,
    summary,
    corrections,
    transparency,
    activeRunState,
    handleArchiveGoal,
    handleCreateGoal,
    handleGoalProgress,
    handleGoalUpdate,
    handlePlanAction,
    handleGoalGenerate,
    handleGoalRunControl,
    handleToggleSource,
    handleDelete,
    handleRevokeCorrection,
    handleMarkInaccurate
  } = useLearningState();

  return (
    <main id="main-content" className="learning-state-page" aria-busy={snapshots.loading || busy}>
      <header className="ls-header">
        <div className="ls-header__title-row">
          <h1 className="ls-title">我的状态</h1>
          <Link className="ls-prediction-link" to="/prediction">查看趋势与方案比较</Link>
        </div>
        <p className="ls-subtitle">根据你授权的学习与校园记录生成，可查看依据并随时纠正</p>
        {snapshots.data?.items?.[0] && (
          <p className="ls-update-time">
            <QualityBadge quality={snapshots.data.items[0].data_quality} />
            <span> · 更新于 {formatRelativeTime(snapshots.data.items[0].computed_at)}</span>
          </p>
        )}
      </header>

      {toast && <div className="ls-toast" aria-live="assertive" role="status">{toast}</div>}

      <ErrorBar error={snapshots.error} />

      <div className="ls-layout">
        <div className="ls-layout__main">
          <StateOverview snapshots={snapshots.data} onViewEvidence={setEvidenceSnapshot} onMarkInaccurate={handleMarkInaccurate} />
          <InterventionLoopSummary
            intervention={currentIntervention}
            outcome={interventionOutcome.data}
            loading={interventionOutcome.loading}
            error={interventionOutcome.error}
            onRetry={interventionOutcome.reload}
          />
          <WorldSnapshotSection snapshots={worldSnapshots.data} onViewEvidence={setEvidenceSnapshot} />
          <StateTimeline changes={changes.data} />
          <ForecastSection forecasts={forecasts.data} />
        </div>
        <div className="ls-layout__side">
          <GoalExecutionCenter goals={goals.data} plans={plans.data} jobs={runtimeJobs.data} summary={planSummary.data} activeRun={activeRunState.run} onGenerate={handleGoalGenerate} onControl={handleGoalRunControl} busy={busy} />
          <LearningPlanCenter plans={plans.data} onAction={handlePlanAction} busy={busy} />
          <GoalsSection goals={goals.data} onArchive={handleArchiveGoal} onCreate={handleCreateGoal} onProgress={handleGoalProgress} onUpdate={handleGoalUpdate} busy={busy} />
        </div>
      </div>

      <div className="ls-layout ls-layout--bottom">
        <div className="ls-layout__main">
          <PlanEvaluationSection plans={plans.data} />
        </div>
        <div className="ls-layout__side">
          <DataPrivacyControl
            controls={controls.data}
            summary={summary.data}
            corrections={corrections.data}
            onToggleSource={handleToggleSource}
            onDelete={handleDelete}
            onRevokeCorrection={handleRevokeCorrection}
            busy={busy}
          />
        </div>
      </div>

      <ModelTransparency transparency={transparency.data} />

      {evidenceSnapshot && <EvidenceDrawer key={evidenceSnapshot.snapshot_id} snapshot={evidenceSnapshot} onClose={() => setEvidenceSnapshot(null)} onCorrection={handleMarkInaccurate} />}
    </main>
  );
}
