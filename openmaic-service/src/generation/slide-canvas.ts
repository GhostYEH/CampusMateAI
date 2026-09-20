/**
 * 幻灯片画布合成器。
 *
 * ## 为什么不让模型直接产出元素布局
 *
 * 绝对坐标排版恰好是模型最不擅长的部分：位置会重叠、越界、尺寸缺失，而这些错误
 * 只有把画布渲染出来才看得见。所以这里把职责切开——
 *
 *   **模型只出结构化内容**（标题、副标题、要点、小节），
 *   **服务端用确定性模板排版**（元素几何、配色、层级）。
 *
 * 好处不只是"好看一点"：同一份内容永远得到同一张画布，于是几何不变量
 * （元素在画布内、标题与正文不重叠、id 唯一、每个元素字段完整）可以在
 * `node --test` 里直接钉住，**不需要调用模型**。模型侧的失败模式因此收窄成
 * "内容为空/字段类型不对"，而不是"排版随机不可测"。
 *
 * ## 画布契约
 *
 * 输出形状与前端移植层 `MaicSlideSurface` 的输入一致：
 * `{ width, height, theme, background, elements }`，`elements` 里每一项都是
 * 参考项目 `PPTBaseElement`（`id/left/top/width/height/rotate`）+ 具体类型的
 * 必填字段。字号、行高、边距一律写成**元素正文的内联样式**，不依赖宿主页面
 * 是否注入了排版 CSS —— 幻灯片 JSON 自己就是唯一权威。
 */

/** 参考项目的设计尺寸：1000 宽、16:9。与 `@openmaic/renderer` 默认一致。 */
export const SLIDE_CANVAS_WIDTH = 1000;
export const SLIDE_CANVAS_HEIGHT = 562.5;

/** 画布版心边距。 */
const MARGIN = 64;
const CONTENT_WIDTH = SLIDE_CANVAS_WIDTH - MARGIN * 2;

/**
 * 文本元素的内边距。参考项目的 `BaseTextElement` 把正文包在
 * `element-content p-[10px]` 里，所以要让**文字**落在 x，元素的 `left`
 * 必须写成 `x - PAD`。不补偿就会整体右下偏移 10px，且相邻元素的对齐会看起来
 * "差一点点"——这类偏差最难被发现，也最容易被当成字体问题。
 */
const TEXT_PAD = 10;

const PALETTE = {
  ink: '#1f2937',
  inkSoft: '#374151',
  muted: '#6b7280',
  accent: '#722ed1',
  accentSoft: '#f5f3ff',
  hairline: '#e5e7eb',
  surface: '#ffffff',
};

const FONT_NAME = 'Microsoft YaHei';

export interface SlideSection {
  heading: string;
  bullets: string[];
}

export interface SlideOutline {
  title: string;
  subtitle: string;
  bullets: string[];
  sections: SlideSection[];
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function stringList(value: unknown, limit: number): string[] {
  if (!Array.isArray(value)) return [];
  return value.map(text).filter(Boolean).slice(0, limit);
}

/**
 * 把模型给的 slide 内容归一成一份 outline。
 *
 * 同时接受两种输入，这是**向后兼容**而不是双份实现：
 * - 新版 `{ slide: { title, subtitle, bullets, sections } }`；
 * - 旧版 `{ canvas: { title, body } }`（历史数据与既有夹具仍在用）。
 *
 * 旧版没有结构化要点，就把 body 按空行/换行切成要点，而不是丢掉——丢掉会让
 * 历史数据在课堂里突然变成一张空幻灯片。
 */
export function readSlideOutline(content: unknown): SlideOutline {
  const source = isObject(content) ? content : {};
  const slide = isObject(source.slide) ? source.slide : undefined;
  const canvas = isObject(source.canvas) ? source.canvas : undefined;

  const title = text(slide?.title) || text(canvas?.title);

  if (slide) {
    const sections = Array.isArray(slide.sections)
      ? slide.sections
          .map((section) => {
            if (!isObject(section)) return null;
            const heading = text(section.heading);
            const bullets = stringList(section.bullets, 6);
            if (!heading && !bullets.length) return null;
            return { heading, bullets };
          })
          .filter((section): section is SlideSection => section !== null)
          .slice(0, 3)
      : [];
    return {
      title,
      subtitle: text(slide.subtitle),
      bullets: stringList(slide.bullets, 8),
      sections,
    };
  }

  const body = text(canvas?.body);
  return {
    title,
    subtitle: '',
    bullets: body
      ? body
          .split(/\n{2,}|\n/)
          .map((line) => line.replace(/^[-•*\d.\s]+/, '').trim())
          .filter(Boolean)
          .slice(0, 8)
      : [],
    sections: [],
  };
}

interface TextElementInput {
  id: string;
  left: number;
  top: number;
  width: number;
  height: number;
  html: string;
  fontSize: number;
  color: string;
  bold?: boolean;
  align?: 'left' | 'center' | 'right';
  vAlign?: 'top' | 'middle' | 'bottom';
  lineHeight?: number;
}

/** 参考项目 `PPTTextElement`。`rotate` 是必填字段，缺了渲染层会读成 undefined。 */
function textElement(input: TextElementInput): Record<string, unknown> {
  return {
    id: input.id,
    type: 'text',
    left: input.left,
    top: input.top,
    width: input.width,
    height: input.height,
    rotate: 0,
    content: input.html,
    defaultFontName: FONT_NAME,
    defaultColor: input.color,
    lineHeight: input.lineHeight ?? 1.4,
    opacity: 1,
    vAlign: input.vAlign ?? 'top',
    textType: 'content',
  };
}

/** 圆角矩形路径。参考项目用 `path` + `viewBox` 画形状，不是 CSS border-radius。 */
function roundedRectPath(width: number, height: number, radius: number): string {
  const r = Math.max(0, Math.min(radius, width / 2, height / 2));
  return [
    `M ${r} 0`,
    `H ${width - r}`,
    `A ${r} ${r} 0 0 1 ${width} ${r}`,
    `V ${height - r}`,
    `A ${r} ${r} 0 0 1 ${width - r} ${height}`,
    `H ${r}`,
    `A ${r} ${r} 0 0 1 0 ${height - r}`,
    `V ${r}`,
    `A ${r} ${r} 0 0 1 ${r} 0`,
    'Z',
  ].join(' ');
}

/** 参考项目 `PPTShapeElement`。`viewBox` 与 `path` 必须同时给。 */
function shapeElement(input: {
  id: string;
  left: number;
  top: number;
  width: number;
  height: number;
  fill: string;
  radius?: number;
}): Record<string, unknown> {
  return {
    id: input.id,
    type: 'shape',
    left: input.left,
    top: input.top,
    width: input.width,
    height: input.height,
    rotate: 0,
    viewBox: [input.width, input.height] as [number, number],
    path: roundedRectPath(input.width, input.height, input.radius ?? 12),
    fill: input.fill,
    opacity: 1,
  };
}

function paragraph(value: string, style: string): string {
  return `<p style="${style}">${escapeHtml(value)}</p>`;
}

function listHtml(bullets: string[], style: string, itemStyle: string): string {
  return `<ul style="${style}">${bullets
    .map((item) => `<li style="${itemStyle}">${escapeHtml(item)}</li>`)
    .join('')}</ul>`;
}

/** 页眉：标题 + 一条强调短线。三种版式共用，保证同一门课的幻灯片有统一顶栏。 */
function headerElements(title: string, baseY: number): Record<string, unknown>[] {
  const elements: Record<string, unknown>[] = [
    textElement({
      id: 'el_title',
      left: MARGIN - TEXT_PAD,
      top: baseY - TEXT_PAD,
      width: CONTENT_WIDTH + TEXT_PAD * 2,
      height: 92,
      html: paragraph(
        title,
        `font-size:36px;line-height:1.25;font-weight:700;margin:0;color:${PALETTE.ink};`,
      ),
      fontSize: 36,
      color: PALETTE.ink,
      bold: true,
    }),
  ];
  if (title) {
    elements.push(
      shapeElement({
        id: 'el_accent',
        // 必须落在**标题元素盒之下**，而不是"一行标题之下"。标题盒留了 92px
        // （够两行 36px/1.25），若按一行的高度放线，标题一换行就会撞上线——
        // 这种重叠只在长标题上偶发，靠肉眼很难稳定复现。
        left: MARGIN,
        top: baseY + 82 + 14,
        width: 64,
        height: 6,
        fill: PALETTE.accent,
        radius: 3,
      }),
    );
  }
  return elements;
}

/** 纯标题页（封面/过渡页）。没有要点时不该留一大块空白。 */
function composeTitleSlide(outline: SlideOutline): Record<string, unknown>[] {
  const elements: Record<string, unknown>[] = [
    shapeElement({
      id: 'el_accent',
      left: SLIDE_CANVAS_WIDTH / 2 - 32,
      top: 168,
      width: 64,
      height: 6,
      fill: PALETTE.accent,
      radius: 3,
    }),
    textElement({
      id: 'el_title',
      left: MARGIN - TEXT_PAD,
      top: 200 - TEXT_PAD,
      width: CONTENT_WIDTH + TEXT_PAD * 2,
      height: 120,
      html: paragraph(
        outline.title || '未命名内容',
        `font-size:44px;line-height:1.3;font-weight:700;margin:0;text-align:center;color:${PALETTE.ink};`,
      ),
      fontSize: 44,
      color: PALETTE.ink,
      bold: true,
      align: 'center',
    }),
  ];
  if (outline.subtitle) {
    elements.push(
      textElement({
        id: 'el_subtitle',
        left: MARGIN - TEXT_PAD,
        top: 330 - TEXT_PAD,
        width: CONTENT_WIDTH + TEXT_PAD * 2,
        height: 60,
        html: paragraph(
          outline.subtitle,
          `font-size:20px;line-height:1.6;margin:0;text-align:center;color:${PALETTE.muted};`,
        ),
        fontSize: 20,
        color: PALETTE.muted,
        align: 'center',
      }),
    );
  }
  return elements;
}

/** 要点页：页眉 + 一条纵向要点列表。 */
function composeBulletsSlide(outline: SlideOutline): Record<string, unknown>[] {
  const elements = headerElements(outline.title, 56);
  const bullets = outline.bullets.length ? outline.bullets : [outline.subtitle || '围绕本页主题展开。'];
  elements.push(
    textElement({
      id: 'el_body',
      left: MARGIN - TEXT_PAD,
      top: 200 - TEXT_PAD,
      width: CONTENT_WIDTH + TEXT_PAD * 2,
      height: SLIDE_CANVAS_HEIGHT - 200 - MARGIN + TEXT_PAD,
      html: listHtml(
        bullets,
        'margin:0;padding-inline-start:28px;',
        `font-size:21px;line-height:1.75;margin-bottom:12px;color:${PALETTE.inkSoft};`,
      ),
      fontSize: 21,
      color: PALETTE.inkSoft,
      lineHeight: 1.75,
    }),
  );
  return elements;
}

/**
 * 小节页：页眉 + 2~3 张并排卡片，每张卡片一个标题 + 若干要点。
 *
 * 卡片是**真实形状元素**而不是 CSS 盒子：参考项目的画布只认元素数组，
 * 用 div 画卡片在幻灯片 JSON 里不存在，导出与编辑都会丢。
 */
function composeSectionsSlide(outline: SlideOutline): Record<string, unknown>[] {
  const sections = outline.sections.slice(0, 3);
  const elements = headerElements(outline.title, 56);
  const gap = 20;
  const cardTop = 196;
  const cardHeight = SLIDE_CANVAS_HEIGHT - cardTop - 56;
  const cardWidth = (CONTENT_WIDTH - gap * (sections.length - 1)) / sections.length;

  sections.forEach((section, index) => {
    const left = MARGIN + index * (cardWidth + gap);
    elements.push(
      shapeElement({
        id: `el_card_${index + 1}`,
        left,
        top: cardTop,
        width: cardWidth,
        height: cardHeight,
        fill: PALETTE.accentSoft,
        radius: 16,
      }),
    );
    if (section.heading) {
      elements.push(
        textElement({
          id: `el_section_${index + 1}_heading`,
          left: left + 18 - TEXT_PAD,
          top: cardTop + 20 - TEXT_PAD,
          width: cardWidth - 36 + TEXT_PAD * 2,
          height: 40,
          html: paragraph(
            section.heading,
            `font-size:18px;line-height:1.4;font-weight:700;margin:0;color:${PALETTE.accent};`,
          ),
          fontSize: 18,
          color: PALETTE.accent,
          bold: true,
        }),
      );
    }
    if (section.bullets.length) {
      elements.push(
        textElement({
          id: `el_section_${index + 1}_body`,
          left: left + 18 - TEXT_PAD,
          top: cardTop + 64 - TEXT_PAD,
          width: cardWidth - 36 + TEXT_PAD * 2,
          height: cardHeight - 84 + TEXT_PAD,
          html: listHtml(
            section.bullets,
            'margin:0;padding-inline-start:22px;',
            `font-size:15px;line-height:1.7;margin-bottom:9px;color:${PALETTE.inkSoft};`,
          ),
          fontSize: 15,
          color: PALETTE.inkSoft,
          lineHeight: 1.7,
        }),
      );
    }
  });
  return elements;
}

/** 版式选择是**确定性**的：内容形状决定版式，同一份内容永远同一张画布。 */
export function composeSlideCanvas(content: unknown): Record<string, unknown> {
  const outline = readSlideOutline(content);
  const elements = outline.sections.length
    ? composeSectionsSlide(outline)
    : outline.bullets.length
      ? composeBulletsSlide(outline)
      : composeTitleSlide(outline);

  return {
    width: SLIDE_CANVAS_WIDTH,
    height: SLIDE_CANVAS_HEIGHT,
    theme: {
      fontColor: PALETTE.ink,
      fontName: FONT_NAME,
      backgroundColor: PALETTE.surface,
    },
    background: { type: 'solid', color: PALETTE.surface },
    elements,
  };
}

/** 版式名。仅用于测试与日志，不进入画布。 */
export function slideLayoutOf(content: unknown): 'title' | 'bullets' | 'sections' {
  const outline = readSlideOutline(content);
  if (outline.sections.length) return 'sections';
  if (outline.bullets.length) return 'bullets';
  return 'title';
}
