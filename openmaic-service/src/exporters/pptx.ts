import type { StageRow } from '../workspace/repository.ts';
import { writeZip } from '../archive/zip.ts';
import { finishExport, orderedScenes, parseStoredDocument, sceneText, xmlEscape, type ExportedDocument } from './shared.ts';

const PRESENTATION_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/></Relationships>`;
const ROOT_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/></Relationships>`;
const MASTER = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld name="Master"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:sldLayoutIdLst/><p:txStyles/></p:sldMaster>`;

function slideXml(title: string, values: string[]): string {
  const text = [title, ...values].filter(Boolean).slice(0, 30);
  const runs = text.map((value, index) => `<a:p><a:r><a:rPr lang="zh-CN"/><a:t>${xmlEscape(value)}</a:t></a:r></a:p>`).join('');
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld name="${xmlEscape(title)}"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/><p:sp><p:nvSpPr><p:cNvPr id="2" name="Text"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>${runs}</p:txBody></p:sp></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>`;
}

export function exportPptx(input: { stage: StageRow; exportedAt: string }): ExportedDocument {
  const document = parseStoredDocument(input.stage);
  const scenes = orderedScenes(document);
  const slideEntries = scenes.map((scene, index) => ({
    name: `ppt/slides/slide${index + 1}.xml`,
    data: Buffer.from(slideXml(String(scene.title || `场景 ${index + 1}`), sceneText(scene).slice(1))),
  }));
  const slideRels = scenes.map((_, index) => ({
    name: `ppt/slides/_rels/slide${index + 1}.xml.rels`,
    data: Buffer.from(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>`),
  }));
  const presentation = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst><p:sldMasterId id="1" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></p:sldMasterIdLst><p:sldIdLst>${scenes.map((_, index) => `<p:sldId id="${256 + index}" r:id="rId${index + 2}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>`).join('')}</p:sldIdLst><p:sldSz cx="12192000" cy="6858000"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>`;
  const contentTypes = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>${scenes.map((_, index) => `<Override PartName="/ppt/slides/slide${index + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>`).join('')}</Types>`;
  const presentationRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>${scenes.map((_, index) => `<Relationship Id="rId${index + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide${index + 1}.xml"/>`).join('')}</Relationships>`;
  const content = writeZip([
    { name: '[Content_Types].xml', data: Buffer.from(contentTypes) },
    { name: '_rels/.rels', data: Buffer.from(ROOT_RELS) },
    { name: 'ppt/presentation.xml', data: Buffer.from(presentation) },
    { name: 'ppt/_rels/presentation.xml.rels', data: Buffer.from(presentationRels) },
    { name: 'ppt/slideMasters/slideMaster1.xml', data: Buffer.from(MASTER) },
    { name: 'ppt/slideMasters/_rels/slideMaster1.xml.rels', data: Buffer.from(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>`) },
    ...slideEntries,
    ...slideRels,
  ], { modifiedAt: new Date(input.exportedAt) });
  return finishExport(content, input.stage, '.pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation');
}
