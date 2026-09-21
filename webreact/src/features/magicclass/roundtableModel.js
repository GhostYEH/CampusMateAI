/**
 * 圆桌讨论的视图模型。
 *
 * 圆桌最容易"看起来像在讨论其实什么都没说"，所以三条规则在这里定死：
 *
 * 1. **发言人颜色由名字派生，不用随机数。** 参考项目从智能体配置里取颜色；本服务
 *    只回 `{agent, content}`，没有配置。用名字派生保证同一个发言人每次、每个回合、
 *    每次刷新都是同一个颜色——随机色会让同一场讨论中同一个人的头像变色。
 * 2. **空发言不进气泡。** 服务端可能回空字符串或只有空白；把它们渲染成空气泡会让
 *    "讨论正在进行"看起来像"界面坏了"。
 * 3. **失败要有可行动的中文说法。** Provider 未配置、服务不可用、任务失败是三种不同
 *    的处置方式，不能都显示成一句"失败"。
 */

/** 发言人头像配色。取自参考项目圆桌的紫/蓝系，顺序固定，因此派生结果稳定。 */
export const SPEAKER_PALETTE = [
  { ring: "#a855f7", bg: "#f3e8ff", text: "#7e22ce" },
  { ring: "#3b82f6", bg: "#dbeafe", text: "#1d4ed8" },
  { ring: "#10b981", bg: "#d1fae5", text: "#047857" },
  { ring: "#f59e0b", bg: "#fef3c7", text: "#b45309" },
  { ring: "#ec4899", bg: "#fce7f3", text: "#be185d" },
  { ring: "#06b6d4", bg: "#cffafe", text: "#0e7490" },
];

/** 单条发言的长度上限。服务端已限过，这里再挡一次，避免一条超长气泡撑爆面板。 */
export const MAX_MESSAGE_CHARS = 600;

/** FNV-1a：跨进程稳定，用来把名字映射到调色板。不用 `Math.random`。 */
function hashText(value) {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash;
}

/** 发言人配色：同名同色，与出现顺序无关。 */
export function speakerColor(name) {
  const key = String(name ?? "").trim() || "智能体";
  return SPEAKER_PALETTE[hashText(key) % SPEAKER_PALETTE.length];
}

/** 名字首字，用作头像里的文字标签（没有真实头像图，也不该去编一张）。 */
export function speakerInitial(name) {
  const key = String(name ?? "").trim();
  return key ? Array.from(key)[0] : "智";
}

/**
 * 归一化讨论结果。接受 `{messages: [...]}` 或直接是数组；两种都出现在不同的调用
 * 路径上（artifact 里是对象，历史记录里是数组）。
 */
export function normalizeDiscussionMessages(payload) {
  const raw = Array.isArray(payload) ? payload : Array.isArray(payload?.messages) ? payload.messages : [];
  return raw
    .map((entry) => {
      if (!entry || typeof entry !== "object") return null;
      const content = String(entry.content ?? "").trim();
      if (!content) return null; // 空发言不进气泡
      return {
        agent: String(entry.agent ?? "").trim() || "智能体",
        content: content.length > MAX_MESSAGE_CHARS ? `${content.slice(0, MAX_MESSAGE_CHARS)}…` : content,
      };
    })
    .filter((entry) => entry !== null);
}

/** 出场顺序去重的发言人列表，用于右侧参与者栏与左侧主讲人。 */
export function discussionSpeakers(messages) {
  const seen = new Map();
  for (const message of messages ?? []) {
    if (!seen.has(message.agent)) seen.set(message.agent, speakerColor(message.agent));
  }
  return Array.from(seen, ([name, color]) => ({ name, color }));
}

/**
 * 面板状态。四态互斥，且**只有真正拿到发言才算 ready**——"任务完成但没有发言"
 * 必须落在 `empty`（并说明没拿到内容），不能显示成"讨论结束"。
 */
export function roundtablePhase({ busy = false, error = "", messages = [] } = {}) {
  if (error) return "failed";
  if (busy) return "running";
  return messages.length ? "ready" : "empty";
}

const FAILURE_COPY = {
  provider_unavailable: "本部署还没有配置讨论用的模型，暂时无法发起圆桌讨论。",
  MAGICCLASS_FUSION_UNAVAILABLE: "暂时连不上受管 magic class 服务，请稍后重试。",
  MAGICCLASS_INVALID_REQUEST: "这次讨论的请求不合法，换个主题再试一次。",
};

/** 把失败翻译成可行动的中文。未知原因也要说清是"哪种未知"，不吞掉原始码。 */
export function describeDiscussionFailure(error) {
  const status = error?.response?.status;
  const code = error?.response?.data?.code;
  const detail = error?.response?.data?.detail || error?.response?.data?.message;

  if (code && FAILURE_COPY[code]) return FAILURE_COPY[code];
  if (status === 503) return FAILURE_COPY.MAGICCLASS_FUSION_UNAVAILABLE;
  if (status === 400) return FAILURE_COPY.MAGICCLASS_INVALID_REQUEST;
  if (status === 404) return "这个课堂已经不存在了，请返回课程列表重新进入。";
  if (detail) return String(detail);
  if (error?.message) return String(error.message);
  return "圆桌讨论没能完成，请稍后重试。";
}

/** 讨论主题：默认用当前场景标题，学员可以改写。 */
export function discussionPromptFor(sceneTitle) {
  const title = String(sceneTitle ?? "").trim();
  return title ? `${title}：请从不同角度讨论这个主题。` : "";
}

/** 提交前校验。与按钮的 disabled 条件同源，避免"按钮亮着但点了没反应"。 */
export function discussionRejection({ prompt, busy }) {
  if (busy) return "上一轮讨论还在进行，请稍候。";
  if (!String(prompt ?? "").trim()) return "请先写下想讨论的主题。";
  return null;
}
