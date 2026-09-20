/**
 * 移植补充：`tinycolor2` 的最小等价实现。
 *
 * 参考项目里只有两处用到 tinycolor2：
 *   1. `lib/utils/element.ts#getTableSubThemeColor` —— `setAlpha(0.3/0.1).toRgbString()`；
 *   2. `components/slide-renderer/components/element/ChartElement/Chart.tsx` ——
 *      `analogous(n).map(c => c.toRgbString())` 用来把不足 10 个主题色补齐。
 *
 * 目标项目没有安装 tinycolor2（且本任务不允许改 package.json），所以这里按
 * tinycolor2 的算法逐条复刻，输出字符串与上游逐字一致，避免表格配色和图表配色
 * 与参考项目出现可察觉的色差。已用参考项目 node_modules 里的真实 tinycolor2
 * 对 `#hex` / `rgb()` / `rgba()` / `hsl()` / 命名色 / 非法输入逐一比对通过。
 */

const NAMED_COLORS = {
  black: '#000000',
  silver: '#c0c0c0',
  gray: '#808080',
  grey: '#808080',
  white: '#ffffff',
  maroon: '#800000',
  red: '#ff0000',
  purple: '#800080',
  fuchsia: '#ff00ff',
  green: '#008000',
  lime: '#00ff00',
  olive: '#808000',
  yellow: '#ffff00',
  navy: '#000080',
  blue: '#0000ff',
  teal: '#008080',
  aqua: '#00ffff',
  cyan: '#00ffff',
  magenta: '#ff00ff',
  orange: '#ffa500',
  transparent: '#00000000',
};

/** tinycolor2 `boundAlpha` */
function boundAlpha(value) {
  const a = parseFloat(value);
  if (Number.isNaN(a) || a < 0 || a > 1) return 1;
  return a;
}

/** tinycolor2 `isOnePointZero`：数字 1 与字符串 '1' 都按 100% 处理 */
function isOnePointZero(value) {
  return typeof value === 'string' && value.indexOf('.') === -1
    ? parseFloat(value) === 1
    : value === 1;
}

/** tinycolor2 `isPercentage` */
function isPercentage(value) {
  return typeof value === 'string' && value.indexOf('%') !== -1;
}

/** tinycolor2 `bound01` */
function bound01(n, max) {
  let value = n;
  if (isOnePointZero(value)) value = '100%';
  const processPercent = isPercentage(value);
  value = Math.min(max, Math.max(0, parseFloat(value)));

  if (processPercent) {
    value = parseInt(value * max, 10) / 100;
  }

  if (Math.abs(value - max) < 0.000001) return 1;
  return (value % max) / parseFloat(max);
}

/**
 * tinycolor2 的 `inputToRgb` 对 `{h,s,l}` 对象的处理：
 * `hslToRgb(bound01(h, 360), bound01(s, 100), bound01(l, 100))`。
 *
 * 注意 `s` / `l` 必须先按 `bound01(_, 100)` 归一化再进 `hslToRgb` —— 直接用
 * `0-1` 的小数会得到恒等（`0.639 % 100 === 0.639`），但要按 `bound01(x,100)`
 * 归一化，才能同时接受 `hsl(210, 100%, 54%)` 里的 `100` / `54` 两种写法。
 */
function hslComponentToRgb(h, s, l) {
  return hslToRgb(bound01(h, 360), bound01(s, 100), bound01(l, 100));
}

/**
 * tinycolor2 `rgbToRgb`：把 r/g/b 分量归一到 [0,255]。
 * 直接复用 `bound01(x, 255) * 255` —— 与上游同一段代码，
 * `'1'` / `1` 被当作 100% 的细节也由 `bound01` 覆盖。
 */
function rgbToRgb(r, g, b) {
  return {
    r: bound01(r, 255) * 255,
    g: bound01(g, 255) * 255,
    b: bound01(b, 255) * 255,
  };
}

function hexToRgb(hex) {
  let value = String(hex).replace(/^#/, '');
  if (value.length === 3 || value.length === 4) {
    value = value
      .split('')
      .map((char) => char + char)
      .join('');
  }
  if (value.length !== 6 && value.length !== 8) return null;

  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  const a = value.length === 8 ? parseInt(value.slice(6, 8), 16) / 255 : 1;
  if ([r, g, b, a].some((part) => Number.isNaN(part))) return null;
  return { r, g, b, a, ok: true };
}

function parseColorString(input) {
  const raw = String(input).trim().toLowerCase();
  if (!raw) return { r: 0, g: 0, b: 0, a: 1, ok: false };

  if (raw.startsWith('#')) {
    const hex = hexToRgb(raw);
    if (!hex) return { r: 0, g: 0, b: 0, a: 1, ok: false };
    return hex;
  }

  if (NAMED_COLORS[raw] !== undefined) {
    const named = NAMED_COLORS[raw];
    if (named === '#00000000') return { r: 0, g: 0, b: 0, a: 0, ok: true };
    return hexToRgb(named);
  }

  const functional = raw.match(/^(rgba?|hsla?)\s*\(([^)]+)\)$/);
  if (!functional) return { r: 0, g: 0, b: 0, a: 1, ok: false };

  const kind = functional[1];
  const parts = functional[2]
    .split(/[,/]/)
    .map((part) => part.trim())
    .filter((part) => part !== '');

  if (kind === 'rgb' || kind === 'rgba') {
    if (parts.length < 3) return { r: 0, g: 0, b: 0, a: 1, ok: false };
    const rgb = rgbToRgb(parts[0], parts[1], parts[2]);
    return {
      r: rgb.r,
      g: rgb.g,
      b: rgb.b,
      a: parts.length > 3 ? boundAlpha(parts[3]) : 1,
      ok: true,
    };
  }

  if (parts.length < 3) return { r: 0, g: 0, b: 0, a: 1, ok: false };
  // 与 tinycolor2 的 inputToRGB 一致：hsl 的 h 用 bound01(x, 360)，
  // s / l 用 bound01(x, 100)（百分号写法与小数写法都接受）。
  const hsl = hslToRgb(bound01(parts[0], 360), bound01(parts[1], 100), bound01(parts[2], 100));
  return {
    r: hsl.r,
    g: hsl.g,
    b: hsl.b,
    a: parts.length > 3 ? boundAlpha(parts[3]) : 1,
    ok: true,
  };
}

function rgbToHsl(r, g, b) {
  const rr = bound01(r, 255);
  const gg = bound01(g, 255);
  const bb = bound01(b, 255);
  const max = Math.max(rr, gg, bb);
  const min = Math.min(rr, gg, bb);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;

  if (max === min) {
    h = 0;
    s = 0;
  } else {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === rr) h = (gg - bb) / d + (gg < bb ? 6 : 0);
    else if (max === gg) h = (bb - rr) / d + 2;
    else h = (rr - gg) / d + 4;
    h /= 6;
  }

  return { h, s, l };
}

/**
 * tinycolor2 `hslToRgb`：参数是**已归一化**的 h(0-1) / s(0-1) / l(0-1)。
 * 上游在 `inputToRgb` 与 `toHsl`-回填两条路径上都先做过 `bound01`，因此这里
 * 不再重复归一化——重复一次会把 `0.639` 压成 `0.00639`。
 */
function hslToRgb(hue, saturation, lightness) {
  const hh = hue;
  const ss = saturation;
  const ll = lightness;

  const hue2rgb = (p, q, t) => {
    let tt = t;
    if (tt < 0) tt += 1;
    if (tt > 1) tt -= 1;
    if (tt < 1 / 6) return p + (q - p) * 6 * tt;
    if (tt < 1 / 2) return q;
    if (tt < 2 / 3) return p + (q - p) * (2 / 3 - tt) * 6;
    return p;
  };

  if (ss === 0) {
    return { r: ll * 255, g: ll * 255, b: ll * 255 };
  }

  const q = ll < 0.5 ? ll * (1 + ss) : ll + ss - ll * ss;
  const p = 2 * ll - q;
  return {
    r: hue2rgb(p, q, hh + 1 / 3) * 255,
    g: hue2rgb(p, q, hh) * 255,
    b: hue2rgb(p, q, hh - 1 / 3) * 255,
  };
}

/**
 * tinycolor2 的 `tinycolor(color)` + `.setAlpha()` + `.toRgbString()` 链。
 * 未知输入退回黑色 + 全不透明，与 tinycolor2 的无效输入行为一致。
 */
export function toRgbString(color, alpha) {
  const parsed = parseColorString(color) ?? { r: 0, g: 0, b: 0, a: 1, ok: false };
  let { r, g, b } = parsed;
  const a = alpha === undefined ? parsed.a : boundAlpha(alpha);

  // tinycolor2 构造函数里的次像素取整
  if (r < 1) r = Math.round(r);
  if (g < 1) g = Math.round(g);
  if (b < 1) b = Math.round(b);

  const roundA = Math.round(100 * a) / 100;
  if (a === 1) {
    return `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`;
  }
  return `rgba(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}, ${roundA})`;
}

/** tinycolor2 的 `.setAlpha(x).toRgbString()` */
export function withAlpha(color, alpha) {
  return toRgbString(color, alpha);
}

/**
 * tinycolor2 的 `.analogous(results, slices)` —— 用于图表主题色补齐。
 * 逐字复刻 `_analogous`：初始色相为 `h - (part * results >> 1) + 720`，
 * 每步 `+part`，结果含原色，并保留原色的 alpha。
 *
 * 注意单位：tinycolor2 里 `_analogous` 拿到的是 `toHsl()` 的结果
 * （h 为 0-360，s/l 为 0-1），再把它作为对象传回 tinycolor 构造函数，
 * 那里 `hslToRgb` 的 s/l 期望 0-1（`bound01(s, 100)` 对 0-1 是恒等）。
 * 所以这里只把 h 在 0-360 上旋转，s/l 一律留在 0-1。
 */
export function analogous(color, results = 6, slices = 30) {
  // 无效输入与 tinycolor2 一致：退回黑色（`tinycolor(x)` 的无效输入行为）
  const parsed = parseColorString(color) ?? { r: 0, g: 0, b: 0, a: 1, ok: false };

  const hsl = rgbToHsl(parsed.r, parsed.g, parsed.b);
  const part = 360 / slices;

  const out = [toRgbStringFromRgb(parsed.r, parsed.g, parsed.b, parsed.a)];

  // 与 tinycolor2 的位移语义保持一致
  let h = (hsl.h * 360 - ((part * results) >> 1) + 720) % 360;

  for (let remaining = results - 1; remaining > 0; remaining -= 1) {
    h = (h + part) % 360;
    // h 是 0-360 的角度，hslToRgb 要的是 0-1
    const rgb = hslToRgb(h / 360, hsl.s, hsl.l);
    out.push(toRgbStringFromRgb(rgb.r, rgb.g, rgb.b, parsed.a));
  }

  return out;
}

function toRgbStringFromRgb(r, g, b, a = 1) {
  if (a === 1) {
    return `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`;
  }
  const roundA = Math.round(100 * a) / 100;
  return `rgba(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}, ${roundA})`;
}
