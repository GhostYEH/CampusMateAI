import type { StageRow } from '../workspace/repository.ts';
import { finishExport, orderedScenes, parseStoredDocument, sceneText, textEscape, type ExportedDocument } from './shared.ts';

export function exportMarkdown(input: { stage: StageRow; exportedAt: string }): ExportedDocument {
  const document = parseStoredDocument(input.stage);
  const title = textEscape(document.stage?.name || input.stage.title) || '学习内容';
  const lines = [`# ${title}`, '', `> 导出时间：${textEscape(input.exportedAt)}`, ''];
  for (const [index, scene] of orderedScenes(document).entries()) {
    lines.push(`## ${index + 1}. ${textEscape(scene.title) || '未命名场景'}`, '');
    const values = sceneText(scene);
    if (scene.type === 'quiz' && values.length > 1) {
      lines.push(`题型：${textEscape(scene.type)}`, '');
      for (const value of values.slice(1)) lines.push(`- ${value}`);
    } else {
      lines.push(...values.slice(1).map((value) => value.startsWith('{') ? `\n\`\`\`json\n${value}\n\`\`\`` : value));
    }
    lines.push('');
  }
  const content = Buffer.from(`${lines.join('\n').trim()}\n`, 'utf8');
  return finishExport(content, input.stage, '.md', 'text/markdown; charset=utf-8');
}
