/**
 * 只有真正进入课堂工作台或生成预览时才收起 CampusMate 的全局导航。
 *
 * `/courses` 是课程/课堂的入口页，仍然属于主站信息架构；如果把它也当成
 * 沉浸式工作台，用户就会同时失去顶部导航和全局搜索，且无法判断自己仍在
 * CampusMate 内。
 */
export function isMagicClassImmersivePath(pathname = "") {
  const segments = pathname.split("/").filter(Boolean);
  if (segments[0] !== "courses" || !segments[1]) return false;
  return segments[2] === "magicclass-preview" || segments[2] === "workspaces";
}
