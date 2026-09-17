/**
 * 课程切换的迟到回写防护。
 *
 * 问题：切换课程 A→B 时，A 的在途请求可能晚于 B 返回。用一个共享的
 * `alive` 布尔量是不够的 —— B 的 effect 会把 `alive` 立刻设回 true，
 * A 的迟到响应于是被误认为有效，覆盖掉 B 的界面状态（成功、失败、finally 三条路径都会中招）。
 *
 * 正确做法：每个异步任务在**出发时**捕获一个 epoch，写回之前确认它仍然是当前 epoch。
 * 课程/会话一变就 `next()`，所有旧 epoch 立即作废。
 */
export function createEpochGuard() {
  let current = 0;
  return {
    get current() {
      return current;
    },
    /** 进入一个新的作用域（如切换课程），返回新的 epoch 并作废所有旧 epoch。 */
    next() {
      current += 1;
      return current;
    },
    /** 作废当前作用域（如组件卸载）。 */
    invalidate() {
      current += 1;
    },
    /** 某个 epoch 是否仍是当前 epoch。 */
    isCurrent(epoch) {
      return epoch === current;
    },
    /**
     * 只有 epoch 仍然有效时才执行写回。
     * 返回是否真的执行了 —— 便于调用方在 finally 里做条件清理。
     */
    runIfCurrent(epoch, fn) {
      if (epoch !== current) return false;
      fn();
      return true;
    },
  };
}

export default createEpochGuard;
