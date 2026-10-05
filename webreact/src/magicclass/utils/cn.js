import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * 与参考项目 `lib/utils/cn.ts` 逐字一致。
 * 放在这里而不是复用站内已有工具，是为了让移植过来的组件保持原样——合并
 * Tailwind 冲突类（`p-2` vs `p-4`）依赖 tailwind-merge 的语义，不能换成普通拼接。
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
