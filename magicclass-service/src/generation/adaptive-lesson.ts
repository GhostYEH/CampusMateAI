import type { Scene } from '../dsl/contract.ts';
import { materializeParameterExperiment, parameterExperimentHtml } from './parameter-experiment.ts';
import { materializeSpatialExperiment, renderSpatialExperiment } from './spatial-experiment.ts';

const ACTIVITY_TYPES = ['simulation', 'visualization3d', 'diagram'];

export const ADAPTIVE_LESSON_GUIDE = [
  '综合课堂（adaptive）：按顺序生成概念讲解、可核对的例子、1–2 个不同的动手场景、最后一页测验。全课 4–8 页，最后的 quiz 至少两道不同的题，其中至少一题要求应用所学。',
  '从学生输入的主题出发，前两页使用下述 slide 小节。动手页给出学生此刻应做什么，以及观察什么；随后用测验检验同一个知识点。',
  '空间构造、方向或相对运动选择 visualization3d；可计算的参数关系选择 simulation；因果、比较、流程或概念关系选择 diagram，让学生点击节点展开证据或解释。只选能帮助理解当前主题的形式，有实质区别时可组合两种。',
  'diagram 的 widgetConfig：{"type":"diagram","description":string,"nodes":[{"label":string,"detail":string},...]}。给出 3–8 个互不相同的节点，detail 具体说明例子、条件或与相邻节点的关系。',
  '综合课堂的互动页只输出 type、widgetType 和 widgetConfig，不写 html、url 或脚本，播放器从数据生成真实交互。专门要求项目实践时，可在动手页之后、测验之前安排一个有明确交付物的 pbl 场景。',
].join('\n');

function record(raw: unknown): raw is Record<string, unknown> {
  return raw !== null && typeof raw === 'object' && !Array.isArray(raw);
}

function text(raw: unknown, limit: number): string {
  if (typeof raw !== 'string') return '';
  const value = raw.trim();
  return value.length <= limit ? value : '';
}

function diagramConfig(raw: unknown) {
  if (!record(raw) || raw.type !== 'diagram' || !Array.isArray(raw.nodes) || raw.nodes.length < 3 || raw.nodes.length > 8) return null;
  const description = text(raw.description, 300);
  if (!description) return null;
  const nodes = [];
  const labels = new Set<string>();
  for (const node of raw.nodes) {
    if (!record(node)) return null;
    const label = text(node.label, 48);
    const detail = text(node.detail, 600);
    if (!label || !detail || labels.has(label)) return null;
    labels.add(label);
    nodes.push({ label, detail });
  }
  return { type: 'diagram', description, nodes };
}

function diagramHtml(config: NonNullable<ReturnType<typeof diagramConfig>>): string {
  const data = JSON.stringify(config).replace(/</g, '\\u003c');
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><style>
*{box-sizing:border-box}body{margin:0;background:#142c2b;color:#f2f1e8;font:16px/1.55 system-ui,sans-serif}
main{max-width:880px;min-height:100vh;margin:auto;padding:clamp(16px,4vw,36px);display:grid;align-content:center;gap:20px}
p,h2{margin:0;overflow-wrap:anywhere}.nodes{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(148px,100%),1fr));gap:10px}
button{font:inherit;text-align:left;color:inherit;background:#234541;border:1px solid #759589;border-radius:9px;min-height:52px;
padding:10px 12px;cursor:pointer;overflow-wrap:anywhere}button[aria-pressed=true]{background:#dab27a;color:#142c2b}
button:focus-visible{outline:2px solid #dab27a;outline-offset:2px}section{display:grid;gap:7px;background:#1c3d36;
padding:16px;border-left:3px solid #dab27a;border-radius:0 8px 8px 0}
</style></head><body><main><p id="activity"></p><div class="nodes" id="nodes" role="group" aria-label="探索知识节点"></div>
<section aria-live="polite"><h2 id="selection"></h2><p id="detail"></p></section></main>
<script type="application/json" id="widget-config">${data}</script><script>
(() => {
  const byId = (id) => document.getElementById(id);
  const config = JSON.parse(byId('widget-config').textContent);
  byId('activity').textContent = config.description;
  const buttons = config.nodes.map((node, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.id = 'node-' + (index + 1);
    button.textContent = node.label;
    button.onclick = () => select(index);
    byId('nodes').append(button);
    return button;
  });
  function select(index) {
    const node = config.nodes[index];
    byId('selection').textContent = node.label;
    byId('detail').textContent = node.detail;
    buttons.forEach((button, position) => button.setAttribute('aria-pressed', String(position === index)));
  }
  select(0);
})();
</script></body></html>`;
}

/** Read only the data for our supported runtimes. Provider HTML is never used by adaptive mode. */
function parseActivity(content: unknown) {
  if (!record(content) || content.type !== 'interactive') return null;
  switch (content.widgetType) {
    case 'simulation': {
      const config = materializeParameterExperiment(content.widgetConfig);
      return config && { widgetType: content.widgetType, config, render: () => parameterExperimentHtml(config) } as const;
    }
    case 'visualization3d': {
      const config = materializeSpatialExperiment(content.widgetConfig);
      return config && { widgetType: content.widgetType, config, render: () => renderSpatialExperiment(config) } as const;
    }
    case 'diagram': {
      const config = diagramConfig(content.widgetConfig);
      return config && { widgetType: content.widgetType, config, render: () => diagramHtml(config) } as const;
    }
    default: return null;
  }
}

export function materializeAdaptiveActivity(content: Scene['content']): Scene['content'] {
  const activity = parseActivity(content);
  if (!activity) return content;
  return { type: 'interactive', widgetType: activity.widgetType, widgetConfig: activity.config, html: activity.render() };
}

export function reviewAdaptiveLesson(scenes: unknown[]): string[] {
  const issues: string[] = [];
  if (scenes.length < 4 || scenes.length > 8) issues.push('综合课堂须有 4–8 页');
  const activities: string[] = [];
  for (const [index, scene] of scenes.entries()) {
    if (!record(scene) || !text(scene.title, 200) || !record(scene.content) || scene.type !== scene.content.type) {
      issues.push(`第 ${index + 1} 页缺少有效标题或场景内容与类型不一致`);
      continue;
    }
    if (scene.type !== 'interactive') continue;
    if (!parseActivity(scene.content)) {
      issues.push(`第 ${index + 1} 页须有可运行的 ${ACTIVITY_TYPES.join('、')} 数据，请按该控件契约修正`);
      continue;
    }
    if (index >= 2 && index < scenes.length - 1) activities.push(String(scene.content.widgetType));
  }
  if (!activities.length || activities.length > 2 || new Set(activities).size !== activities.length) {
    issues.push('在讲解和测验之间安排 1–2 个类型各异的动手场景');
  }
  const last = scenes.at(-1);
  const questions = record(last) && last.type === 'quiz' && record(last.content) && Array.isArray(last.content.questions)
    ? last.content.questions : [];
  const stems = questions.map((question) => record(question) ? text(question.question, 2000) : '').filter(Boolean);
  if (new Set(stems).size < 2) issues.push('最后一页须为 quiz，含至少两道不同的题与各自的解析');
  return issues;
}
