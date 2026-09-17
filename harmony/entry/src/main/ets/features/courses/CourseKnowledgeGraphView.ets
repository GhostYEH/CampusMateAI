import { CourseKnowledgeGraph, KnowledgePoint } from '../../data/Models';

/**
 * 知识点掌握的展示口径。
 *
 * 抽成纯逻辑是为了可测：Harmony 的 hvigor 在部分环境不可用，把口径放在
 * UI 组件里就只能靠肉眼。这里的规则必须与后端/世界模型一致：
 * `mastery_gap_vs_class` 正数表示领先班级平均，负数表示落后。
 */
export class CourseKnowledgeGraphView {
  static rateText(value?: number): string {
    if (value === undefined) return '—';
    return `${value}%`;
  }

  static gapText(value?: number): string {
    if (value === undefined) return '—';
    return value > 0 ? `+${value}` : `${value}`;
  }

  static gapLabel(value?: number): string {
    if (value !== undefined && value < 0) return '落后班级';
    return '领先班级';
  }

  static barWidth(value?: number): string {
    const clamped: number = Math.max(0, Math.min(100, value ?? 0));
    return `${clamped}%`;
  }

  static countLabel(graph?: CourseKnowledgeGraph): string {
    if (graph?.available !== true) return '尚未同步';
    return `${graph?.knowledge_point_count ?? 0} 个知识点`;
  }

  static points(graph?: CourseKnowledgeGraph): KnowledgePoint[] {
    return graph?.points ?? [];
  }

  static tagsText(graph?: CourseKnowledgeGraph): string {
    return (graph?.tags ?? []).join(' · ');
  }

  static pointsToggleLabel(graph: CourseKnowledgeGraph | undefined, expanded: boolean): string {
    if (expanded) return '收起知识点';
    return `查看 ${CourseKnowledgeGraphView.points(graph).length} 个知识点`;
  }

  static unavailableHint(error: string): string {
    if (error.length > 0) return error;
    return '这门课还没有知识点数据。知识图谱属于深度同步内容，需从学习通课程图谱页拉取。';
  }
}
