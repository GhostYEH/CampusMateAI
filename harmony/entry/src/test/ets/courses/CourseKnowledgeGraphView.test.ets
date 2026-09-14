import { describe, expect, it } from '@ohos/hypium';
import { CourseKnowledgeGraph } from '../../../main/ets/data/Models';
import { CourseKnowledgeGraphView } from '../../../main/ets/features/courses/CourseKnowledgeGraphView';

export default function courseKnowledgeGraphViewTest(): void {
  describe('CourseKnowledgeGraphView', () => {
    const graph: CourseKnowledgeGraph = {
      course_id: 'crs_demo',
      available: true,
      synced_at: '2026-09-14T15:27:12+00:00',
      knowledge_point_count: 21,
      own_mastery_rate: 87.5,
      class_mastery_rate: 69,
      mastery_gap_vs_class: 18.5,
      own_completion_rate: 100,
      class_completion_rate: 97,
      tags: ['考点', '重点'],
      points: [
        { external_id: '166601055', name: '二重积分·计算', position: 0 },
        { external_id: '166601056', name: '第一类曲线积分计算', position: 1 }
      ]
    };

    it('renders course level stats from the backend payload', 0, () => {
      expect(CourseKnowledgeGraphView.countLabel(graph)).assertEqual('21 个知识点');
      expect(CourseKnowledgeGraphView.rateText(graph.own_mastery_rate)).assertEqual('87.5%');
      expect(CourseKnowledgeGraphView.rateText(graph.class_mastery_rate)).assertEqual('69%');
    });

    it('treats a positive gap as leading the class', 0, () => {
      expect(CourseKnowledgeGraphView.gapText(18.5)).assertEqual('+18.5');
      expect(CourseKnowledgeGraphView.gapLabel(18.5)).assertEqual('领先班级');
      expect(CourseKnowledgeGraphView.gapText(-12)).assertEqual('-12');
      expect(CourseKnowledgeGraphView.gapLabel(-12)).assertEqual('落后班级');
    });

    it('clamps progress bars and renders a dash for missing data', 0, () => {
      expect(CourseKnowledgeGraphView.barWidth(87.5)).assertEqual('87.5%');
      expect(CourseKnowledgeGraphView.barWidth(140)).assertEqual('100%');
      expect(CourseKnowledgeGraphView.barWidth(-5)).assertEqual('0%');
      expect(CourseKnowledgeGraphView.barWidth(undefined)).assertEqual('0%');
      expect(CourseKnowledgeGraphView.rateText(undefined)).assertEqual('—');
      expect(CourseKnowledgeGraphView.gapText(undefined)).assertEqual('—');
    });

    it('guides the user to sync when the course has no graph yet', 0, () => {
      const empty: CourseKnowledgeGraph = { course_id: 'crs_demo', available: false, knowledge_point_count: 0 };
      expect(CourseKnowledgeGraphView.countLabel(empty)).assertEqual('尚未同步');
      expect(CourseKnowledgeGraphView.countLabel(undefined)).assertEqual('尚未同步');
      expect(CourseKnowledgeGraphView.points(empty).length).assertEqual(0);
      expect(CourseKnowledgeGraphView.unavailableHint('')).assertEqual('这门课还没有知识点数据。知识图谱属于深度同步内容，需从学习通课程图谱页拉取。');
      expect(CourseKnowledgeGraphView.unavailableHint('知识点同步失败，请稍后重试')).assertEqual('知识点同步失败，请稍后重试');
    });

    it('lists knowledge points and their toggle label', 0, () => {
      expect(CourseKnowledgeGraphView.points(graph).length).assertEqual(2);
      expect(CourseKnowledgeGraphView.points(graph)[0].name).assertEqual('二重积分·计算');
      expect(CourseKnowledgeGraphView.pointsToggleLabel(graph, false)).assertEqual('查看 2 个知识点');
      expect(CourseKnowledgeGraphView.pointsToggleLabel(graph, true)).assertEqual('收起知识点');
      expect(CourseKnowledgeGraphView.tagsText(graph)).assertEqual('考点 · 重点');
    });
  });
}
