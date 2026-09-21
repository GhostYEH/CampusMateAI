import type { StageRow } from '../workspace/repository.ts';
import { writeZip } from '../archive/zip.ts';
import { finishExport, orderedScenes, parseStoredDocument, sceneText, xmlEscape, type ExportedDocument } from './shared.ts';

const CONTENT_TYPES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>`;
const RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>`;
const DOCUMENT_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>`;

function paragraph(value: string, style = ''): string {
  const property = style ? `<w:pPr><w:pStyle w:val="${style}"/></w:pPr>` : '';
  return `<w:p>${property}<w:r><w:t xml:space="preserve">${xmlEscape(value)}</w:t></w:r></w:p>`;
}

export function exportDocx(input: { stage: StageRow; exportedAt: string }): ExportedDocument {
  const document = parseStoredDocument(input.stage);
  const paragraphs = [paragraph(document.stage?.name || input.stage.title, 'Title'), paragraph(`导出时间：${input.exportedAt}`)];
  for (const [index, scene] of orderedScenes(document).entries()) {
    paragraphs.push(paragraph(`${index + 1}. ${scene.title}`, 'Heading1'));
    for (const value of sceneText(scene).slice(1)) paragraphs.push(paragraph(value));
  }
  const xml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>${paragraphs.join('')}<w:sectPr/></w:body></w:document>`;
  const content = writeZip([
    { name: '[Content_Types].xml', data: Buffer.from(CONTENT_TYPES) },
    { name: '_rels/.rels', data: Buffer.from(RELS) },
    { name: 'word/document.xml', data: Buffer.from(xml) },
    { name: 'word/_rels/document.xml.rels', data: Buffer.from(DOCUMENT_RELS) },
  ], { modifiedAt: new Date(input.exportedAt) });
  return finishExport(content, input.stage, '.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document');
}
