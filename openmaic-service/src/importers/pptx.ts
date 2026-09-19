import { readZip } from '../archive/zip.ts';
import { WorkspaceError } from '../workspace/errors.ts';
import { DSL_LIMITS } from '../dsl/limits.ts';

const MAX_PPTX_BYTES = 4 * 1024 * 1024;
const MAX_SLIDES = 50;
const MAX_SLIDE_XML_BYTES = 512 * 1024;

function xmlText(xml: string): string[] {
  return [...xml.matchAll(/<a:t(?:\s[^>]*)?>([\s\S]*?)<\/a:t>/gi)]
    .map((match) => match[1].replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').trim())
    .filter(Boolean)
    .slice(0, 30);
}

export function importPptx(content: Buffer, options: { title: string }): { stage: Record<string, any>; scenes: Record<string, any>[] } {
  if (!Buffer.isBuffer(content) || content.length === 0) throw new WorkspaceError('invalid_request', 'pptx is empty');
  if (content.length > MAX_PPTX_BYTES) throw new WorkspaceError('document_rejected', `pptx exceeds ${MAX_PPTX_BYTES} bytes`);
  let entries;
  try {
    entries = readZip(content);
  } catch (error) {
    throw new WorkspaceError('document_rejected', `pptx is not a readable archive: ${error instanceof Error ? error.message : 'invalid zip'}`);
  }
  const slides = entries
    .filter((entry) => /^ppt\/slides\/slide\d+\.xml$/i.test(entry.name))
    .sort((left, right) => Number(left.name.match(/(\d+)/)?.[1]) - Number(right.name.match(/(\d+)/)?.[1]));
  if (slides.length === 0) throw new WorkspaceError('document_rejected', 'pptx contains no slides');
  if (slides.length > MAX_SLIDES) throw new WorkspaceError('document_rejected', `pptx contains more than ${MAX_SLIDES} slides`);
  const stageId = `stage_pptx_import`;
  const title = String(options.title || '导入的课件').trim().slice(0, 200) || '导入的课件';
  const scenes = slides.map((entry, index) => {
    if (entry.data.length > MAX_SLIDE_XML_BYTES) throw new WorkspaceError('document_rejected', 'pptx slide is too large');
    const values = xmlText(entry.data.toString('utf8'));
    const sceneTitle = values.shift() || `第 ${index + 1} 页`;
    return {
      id: `scene_pptx_${index + 1}`,
      stageId,
      title: sceneTitle.slice(0, DSL_LIMITS.maxStringLength),
      order: index + 1,
      type: 'slide',
      content: { type: 'slide', canvas: { text: values } },
    };
  });
  return {
    stage: { id: stageId, name: title, createdAt: Date.now(), updatedAt: Date.now() },
    scenes,
  };
}

export const PPTX_IMPORT_LIMITS = { maxBytes: MAX_PPTX_BYTES, maxSlides: MAX_SLIDES, maxSlideXmlBytes: MAX_SLIDE_XML_BYTES } as const;
