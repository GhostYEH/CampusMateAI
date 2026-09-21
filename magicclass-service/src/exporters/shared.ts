import { createHash } from 'node:crypto';

import type { StageRow } from '../workspace/repository.ts';
import { WorkspaceError } from '../workspace/errors.ts';

export interface ExportedDocument {
  content: Buffer;
  filename: string;
  stageTitle: string;
  byteSize: number;
  sha256: string;
  mediaType: string;
}

export const MAX_FORMAT_EXPORT_BYTES = 2 * 1024 * 1024;

export function parseStoredDocument(stage: StageRow): Record<string, any> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(stage.document);
  } catch {
    throw new WorkspaceError('document_rejected', 'stored stage document is not valid JSON');
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new WorkspaceError('document_rejected', 'stored stage document is not an object');
  }
  return parsed as Record<string, any>;
}

export function safeFilename(title: string, extension: string): string {
  const cleaned = String(title ?? '')
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, ' ')
    .trim()
    .slice(0, 80);
  return `${cleaned || '学习内容'}${extension}`;
}

export function xmlEscape(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

export function textEscape(value: unknown): string {
  return String(value ?? '')
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, '')
    .replace(/<[^>]*>/g, '')
    .trim();
}

export function finishExport(
  content: Buffer,
  stage: StageRow,
  extension: string,
  mediaType: string,
): ExportedDocument {
  if (content.length > MAX_FORMAT_EXPORT_BYTES) {
    throw new WorkspaceError('document_rejected', `export exceeds ${MAX_FORMAT_EXPORT_BYTES} bytes`);
  }
  return {
    content,
    filename: safeFilename(stage.title, extension),
    stageTitle: stage.title,
    byteSize: content.length,
    sha256: createHash('sha256').update(content).digest('hex'),
    mediaType,
  };
}

export function orderedScenes(document: Record<string, any>): Record<string, any>[] {
  return Array.isArray(document.scenes)
    ? [...document.scenes].sort((left, right) => Number(left?.order ?? 0) - Number(right?.order ?? 0))
    : [];
}

export function sceneText(scene: Record<string, any>): string[] {
  const content = scene.content ?? {};
  const values: string[] = [textEscape(scene.title)];
  if (content.type === 'quiz' && Array.isArray(content.questions)) {
    for (const question of content.questions) {
      values.push(textEscape(question?.question));
      for (const option of Array.isArray(question?.options) ? question.options : []) {
        values.push(`${textEscape(option?.label)} (${textEscape(option?.value)})`);
      }
    }
  } else if (content.type === 'interactive') {
    if (content.widgetType) values.push(`组件：${textEscape(content.widgetType)}`);
    if (content.url) values.push(`链接：${textEscape(content.url)}`);
    if (content.html) values.push(textEscape(content.html));
  } else if (content.type === 'slide' || content.type === 'pbl') {
    const serialized = JSON.stringify(content.canvas ?? content, null, 2);
    if (serialized) values.push(textEscape(serialized));
  }
  return values.filter(Boolean);
}
