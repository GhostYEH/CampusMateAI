/**
 * 讲义的 CampusMate 主题映射。
 *
 * magic class 生成的画布可能带自己的主题，也可能只有一页纯白底。这里只做两件事，
 * 不改真实画布结构：
 *   1. 白底/无底色 → 米白，避免课堂里出现刺眼的纯白矩形；
 *   2. 默认的 #333/#000 字色 → 深绿；深色底则用米白字。
 * 显式的品牌色或用户主题原样保留。
 */

export const CAMPUS_INK = "#153B34";
export const CAMPUS_PAPER = "#F2F1E8";
export const CAMPUS_AMBER = "#DAB27A";
export const CAMPUS_COPPER = "#AD6845";

export const CAMPUS_SLIDE_THEME = {
  fontColor: CAMPUS_INK,
  fontName: "Microsoft YaHei",
};

export function normalizeColor(value) {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

export function isNearWhite(value) {
  const color = normalizeColor(value);
  return ["#fff", "#ffffff", "white", "rgb(255,255,255)", "rgba(255,255,255,1)"].includes(color);
}

export function isDarkColor(value) {
  const color = normalizeColor(value);
  if (!/^#[0-9a-f]{6}$/.test(color)) return false;
  const r = parseInt(color.slice(1, 3), 16);
  const g = parseInt(color.slice(3, 5), 16);
  const b = parseInt(color.slice(5, 7), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) < 128;
}

export function campusBackground(background) {
  if (!background) return { type: "solid", color: CAMPUS_PAPER };
  // 旧导入链路可能产出 `{ type: "color" }`（渲染器只认 solid），先归一成 solid，
  // 否则白底不会被映射，课堂里会重新出现刺眼的白板。
  if (background.type === "color" && typeof background.color === "string") {
    return { type: "solid", color: isNearWhite(background.color) ? CAMPUS_PAPER : background.color };
  }
  if (background.type === "solid" && isNearWhite(background.color)) {
    return { ...background, color: CAMPUS_PAPER };
  }
  return background;
}

const LEGACY_DARK_TEXT = ["#333333", "#000000", "#111111", "#111827", "#1f2937", "#222222"];

/** 只改文字元素的默认深灰/黑色，不动形状、图表或用户显式选的品牌色。 */
export function campusElements(elements, ink = CAMPUS_INK) {
  if (!Array.isArray(elements)) return elements;
  return elements.map((element) => {
    if (element?.type !== "text") return element;
    const color = normalizeColor(element.defaultColor);
    if (!color || LEGACY_DARK_TEXT.includes(color)) return { ...element, defaultColor: ink };
    return element;
  });
}

export function campusTheme(theme, background) {
  const dark = background?.type === "solid" && isDarkColor(background.color);
  const ink = dark ? CAMPUS_PAPER : CAMPUS_INK;
  const explicitColor = normalizeColor(theme?.fontColor);
  const keepExplicit = explicitColor && explicitColor !== "#333333" && explicitColor !== "#000000";
  return {
    ...theme,
    fontColor: keepExplicit ? theme.fontColor : ink,
    fontName: theme?.fontName ?? CAMPUS_SLIDE_THEME.fontName,
  };
}
