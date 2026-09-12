import { describe, expect, it } from '@ohos/hypium';
import { AgentEventReducer, IdempotencyKey, AgentRunView } from '../../../main/ets/service/AgentEventReducer';
import {
  AgentEvent, AgentEventType, RunStatus, RunPhase,
  AgentDtoParser, CourseResearchRun, CourseResearchSource, CitationVerification,
  AcademicPolicy, AssistanceMode, AgentArtifact, ArtifactType
} from '../../../main/ets/data/AgentRuntimeModels';

function evt(id: string, seq: number, type: AgentEventType, status: RunStatus,
  phase: RunPhase, role: string, summary: string, artifactId: string | null): AgentEvent {
  return {
    id: id, type: type, run_id: 'run_cr', sequence: seq, status: status, phase: phase,
    role: role, summary: summary, progress: null,
    artifact_id: artifactId, approval_id: null, created_at: '2026-09-12T11:00:00+08:00'
  };
}

export default function courseResearchStateTest(): void {
  describe('CourseResearch golden flow', () => {
    it('question -> roles -> fallback -> partial -> artifact produces partial view', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_cr');
      view = AgentEventReducer.append(view, evt('e1', 1, AgentEventType.RUN_STARTED, RunStatus.RUNNING, RunPhase.CONTEXT_BUILDING, 'coordinator', '分解研究问题', null));
      view = AgentEventReducer.append(view, evt('e5', 5, AgentEventType.MODEL_STARTED, RunStatus.RUNNING, RunPhase.WAITING_FOR_MODEL, 'course_researcher', '检索课程资料', null));
      view = AgentEventReducer.append(view, evt('e10', 10, AgentEventType.MODEL_FALLBACK, RunStatus.RUNNING, RunPhase.WAITING_FOR_MODEL, 'web_researcher', 'Xunfei 不可用,降级到规则检索', null));
      view = AgentEventReducer.append(view, evt('e20', 20, AgentEventType.RUN_PARTIAL, RunStatus.PARTIAL, RunPhase.IDLE, 'synthesizer', '部分来源不可用,已生成带标注的报告', 'art_cr_report'));

      expect(view.status).assertEqual(RunStatus.PARTIAL);
      expect(view.partial).assertEqual(true);
      expect(view.artifactId).assertEqual('art_cr_report');
      expect(view.failed).assertEqual(false);
    });

    it('parses source policy and academic policy from fixture shape', 0, () => {
      const raw: Record<string, Object> = {
        run_id: 'run_cr', user_id: 'user_demo_001', question: '解释快速排序',
        course_id: 'course_x', assistance_mode: 'EXPLAIN', academic_policy: 'LIMITED',
        source_policy: { course_material_priority: true, allow_web: true, allow_user_upload: true },
        status: 'PARTIAL', created_at: '', updated_at: '', artifact_ids: ['art_cr_report']
      };
      const run: CourseResearchRun = AgentDtoParser.courseResearchRun(raw);
      expect(run.academic_policy).assertEqual(AcademicPolicy.LIMITED);
      expect(run.assistance_mode).assertEqual(AssistanceMode.EXPLAIN);
      expect(run.source_policy.course_material_priority).assertEqual(true);
    });

    it('parses citation verification states including PARTIAL', 0, () => {
      const verified: CourseResearchSource = AgentDtoParser.courseResearchSource({
        source_id: 's1', run_id: 'run_cr', title: '课程讲义', url: 'u1',
        verification: 'VERIFIED', is_course_material: true, retrieved_at: ''
      });
      const partial: CourseResearchSource = AgentDtoParser.courseResearchSource({
        source_id: 's2', run_id: 'run_cr', title: '网络资料', url: 'u2',
        verification: 'PARTIAL', is_course_material: false, retrieved_at: ''
      });
      expect(verified.verification).assertEqual(CitationVerification.VERIFIED);
      expect(partial.verification).assertEqual(CitationVerification.PARTIAL);
    });

    it('parses research report artifact with markdown mime type', 0, () => {
      const raw: Record<string, Object> = {
        artifact_id: 'art_cr_report', run_id: 'run_cr', user_id: 'user_demo_001',
        artifact_type: 'COURSE_RESEARCH_REPORT', version: 1, mime_type: 'text/markdown',
        size_bytes: 8192, content_hash: 'sha256:course_research_hash',
        download_url: '/api/v1/agent-artifacts/art_cr_report', created_at: ''
      };
      const art: AgentArtifact = AgentDtoParser.artifact(raw);
      expect(art.artifact_type).assertEqual(ArtifactType.COURSE_RESEARCH_REPORT);
      expect(art.mime_type).assertEqual('text/markdown');
    });

    it('uses stable Idempotency-Key for research run', 0, () => {
      const key: string = IdempotencyKey.forResearchRun('course_x', 'hash1');
      expect(key).assertEqual('cr:run:course_x:hash1');
    });

    it('does not expose model prompt or hidden reasoning in event summary', 0, () => {
      let view: AgentRunView = AgentEventReducer.initial('run_cr');
      view = AgentEventReducer.append(view, evt('e1', 1, AgentEventType.MODEL_COMPLETED, RunStatus.RUNNING, RunPhase.VALIDATING_OUTPUT, 'synthesizer', '已生成带标注的报告', null));
      expect(view.lastSummary.indexOf('prompt') < 0).assertEqual(true);
      expect(view.lastSummary.indexOf('hidden') < 0).assertEqual(true);
    });
  });
}