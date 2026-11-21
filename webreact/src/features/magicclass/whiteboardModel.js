/**
 * 白板快照的纯函数层。
 *
 * 这些函数不碰 DOM、不调 API，课堂组件只负责把「服务端文档」和「用户编辑」
 * 翻译成一份完整快照。把它们抽出来，测试才能直接钉住三件事：
 *
 * 1. 白板来自 `document.stage.whiteboard`，不是前端凭空创建；
 * 2. 没有白板时只创建一个合法的空快照，不用占位元素冒充内容；
 * 3. 文本卡有稳定 id，且元素数量有上限，避免一次点击写入无限大 payload。
 */

export const MAX_WHITEBOARD_ELEMENTS = 2000;
export const MAX_WHITEBOARD_TEXT = 600;

const DEFAULT_VIEWPORT_SIZE = 1000;
const DEFAULT_VIEWPORT_RATIO = 9 / 16;

function validBoard(candidate) {
  if (!candidate || typeof candidate !== "object") return false;
  if (typeof candidate.id !== "string" || !candidate.id.trim()) return false;
  if (!Array.isArray(candidate.elements)) return false;
  return typeof candidate.viewportSize === "number" && candidate.viewportSize > 0
    && typeof candidate.viewportRatio === "number" && candidate.viewportRatio > 0;
}

/**
 * 舞台文档里的第一个白板快照。`scene.whiteboards` 可能是旧格式的引用，也可能是
 * 完整快照；只有带 `elements` 数组的那个才可渲染，引用类数据不冒充白板。
 */
export function whiteboardFromStageDocument(stageDocument) {
  const stageBoards = stageDocument?.document?.stage?.whiteboard;
  if (Array.isArray(stageBoards)) {
    const board = stageBoards.find(validBoard);
    if (board) return cloneBoard(board);
  }
    const sceneBoards = stageDocument?.document?.scenes?.find((scene) => Array.isArray(scene?.whiteboards))?.whiteboards;
  if (Array.isArray(sceneBoards)) {
    const board = sceneBoards.find(validBoard);
    if (board) return cloneBoard(board);
  }
  return blankWhiteboard();
}

export function blankWhiteboard() {
  return {
    id: "whiteboard_1",
    viewportSize: DEFAULT_VIEWPORT_SIZE,
    viewportRatio: DEFAULT_VIEWPORT_RATIO,
    elements: [],
  };
}

export function cloneBoard(board) {
  return {
    ...board,
    elements: Array.isArray(board?.elements) ? board.elements.map((element) => ({ ...element })) : [],
  };
}

/**
 * 往白板追加一张文字卡。坐标按已有卡片数量错开，避免所有卡片叠在同一个位置。
 * `id` 由调用方提供（浏览器用 `crypto.randomUUID`，测试传固定值），这样同一份
 * 快照可以稳定重放。
 */
export function addWhiteboardText(board, text, id) {
  const content = String(text || "").trim();
  if (!content) throw new Error("白板文字不能为空");
  if (content.length > MAX_WHITEBOARD_TEXT) throw new Error(`白板文字最多 ${MAX_WHITEBOARD_TEXT} 字`);
  if (!validBoard(board)) throw new Error("白板快照不合法");
  if (board.elements.length >= MAX_WHITEBOARD_ELEMENTS) throw new Error("白板元素过多");
  const offset = (board.elements.length % 12) * 18;
  const element = {
    id: String(id || "").trim() || `wb-text-${Date.now()}`,
    type: "text",
    left: 72 + offset,
    top: 72 + offset,
    width: 420,
    height: 88,
    rotate: 0,
    opacity: 1,
    defaultColor: "#153B34",
    defaultFontName: "PingFang SC",
    lineHeight: 1.5,
    content: `<p style="margin:0;font-size:20px;line-height:1.5">${escapeHtml(content)}</p>`,
  };
  return { ...board, elements: [...board.elements, element] };
}

export function clearWhiteboard(board) {
  if (!validBoard(board)) throw new Error("白板快照不合法");
  return { ...board, elements: [] };
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
