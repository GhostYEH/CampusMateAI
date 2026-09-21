import { readZip } from '../archive/zip.ts';
import { WorkspaceError } from '../workspace/errors.ts';
import { DSL_LIMITS } from '../dsl/limits.ts';

const MAX_PPTX_BYTES = 4 * 1024 * 1024;
const MAX_SLIDES = 50;
const MAX_SLIDE_XML_BYTES = 512 * 1024;
const MAX_IMAGE_BYTES = 512 * 1024;
const MAX_IMAGES_PER_SLIDE = 8;

function attr(tag: string, name: string): string | undefined {
  const match = new RegExp(`${name}\\s*=\\s*["']([^"']*)["']`, 'i').exec(tag);
  return match?.[1];
}

function numberAttr(tag: string, name: string): number | undefined {
  const value = Number(attr(tag, name));
  return Number.isFinite(value) ? value : undefined;
}

function xmlText(xml: string): string[] {
  return [...xml.matchAll(/<a:t(?:\s[^>]*)?>([\s\S]*?)<\/a:t>/gi)]
    .map((match) => match[1].replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').trim())
    .filter(Boolean)
    .slice(0, 30);
}

function relationshipTargets(xml: string): Map<string, string> {
  const result = new Map<string, string>();
  for (const match of xml.matchAll(/<Relationship\b[^>]*>/gi)) {
    const id = attr(match[0], 'Id');
    const target = attr(match[0], 'Target');
    if (id && target) result.set(id, target);
  }
  return result;
}

function mediaEntryName(target: string): string {
  const normalized = target.replaceAll('\\', '/').replace(/^\.\//, '');
  if (normalized.startsWith('../')) return `ppt/${normalized.slice(3)}`;
  return normalized.startsWith('ppt/') ? normalized : `ppt/${normalized}`;
}

function mediaTypeFor(name: string): string | null {
  const extension = name.toLowerCase().split('.').pop();
  return ({ png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif', webp: 'image/webp' } as Record<string, string>)[extension || ''] || null;
}

function slideElements(xml: string, entries: Array<{ name: string; data: Buffer }>, rels: Map<string, string>): Record<string, unknown>[] {
  const elements: Record<string, unknown>[] = [];
  for (const match of xml.matchAll(/<p:sp\b[\s\S]*?<\/p:sp>/gi)) {
    const block = match[0];
    const values = xmlText(block);
    if (!values.length) continue;
    const transform = /<a:xfrm\b[\s\S]*?<\/a:xfrm>/i.exec(block)?.[0] || '';
    elements.push({
      kind: 'text',
      text: values.join(' '),
      ...(numberAttr(transform, 'x') === undefined ? {} : { x: numberAttr(transform, 'x') }),
      ...(numberAttr(transform, 'y') === undefined ? {} : { y: numberAttr(transform, 'y') }),
      ...(numberAttr(transform, 'cx') === undefined ? {} : { width: numberAttr(transform, 'cx') }),
      ...(numberAttr(transform, 'cy') === undefined ? {} : { height: numberAttr(transform, 'cy') }),
    });
  }
  for (const match of xml.matchAll(/<p:pic\b[\s\S]*?<\/p:pic>/gi)) {
    if (elements.filter((element) => element.kind === 'image').length >= MAX_IMAGES_PER_SLIDE) break;
    const embed = /<a:blip\b[^>]*>/i.exec(match[0])?.[0];
    const target = embed ? rels.get(attr(embed, 'r:embed') || '') : undefined;
    const entryName = target ? mediaEntryName(target) : '';
    const entry = entries.find((candidate) => candidate.name === entryName);
    const mediaType = mediaTypeFor(entryName);
    if (!entry || !mediaType || entry.data.length > MAX_IMAGE_BYTES) continue;
    elements.push({ kind: 'image', mediaType, dataUri: `data:${mediaType};base64,${entry.data.toString('base64')}` });
  }
  return elements;
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
    const slideXml = entry.data.toString('utf8');
    const relsName = `ppt/slides/_rels/slide${index + 1}.xml.rels`;
    const relsEntry = entries.find((candidate) => candidate.name === relsName);
    const elements = slideElements(slideXml, entries, relsEntry ? relationshipTargets(relsEntry.data.toString('utf8')) : new Map());
    return {
      id: `scene_pptx_${index + 1}`,
      stageId,
      title: sceneTitle.slice(0, DSL_LIMITS.maxStringLength),
      order: index + 1,
      type: 'slide',
      content: { type: 'slide', canvas: { width: 1280, height: 720, text: values, elements } },
    };
  });
  return {
    stage: { id: stageId, name: title, createdAt: Date.now(), updatedAt: Date.now() },
    scenes,
  };
}

export const PPTX_IMPORT_LIMITS = { maxBytes: MAX_PPTX_BYTES, maxSlides: MAX_SLIDES, maxSlideXmlBytes: MAX_SLIDE_XML_BYTES, maxImageBytes: MAX_IMAGE_BYTES, maxImagesPerSlide: MAX_IMAGES_PER_SLIDE } as const;
