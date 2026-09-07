export const SUMMER_NAV_LINKS = Object.freeze([
  { to: "/island", label: "小岛" },
  { to: "/plans", label: "计划" },
  { to: "/docs", label: "阅读" },
  { to: "/statistics", label: "主页" },
]);

export function isSummerNavActive(pathname, target) {
  return pathname === target || pathname.startsWith(`${target}/`);
}
