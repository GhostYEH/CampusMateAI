import { useSyncExternalStore } from "react";

/**
 * 极简的 zustand 兼容 store（只实现移植层真正用到的那部分 API）。
 *
 * 参考项目用 zustand 管理交互式 iframe 池、widget 消息、场景运行时错误和 stage。
 * 目标项目不允许引入 zustand，但**调用签名必须保持一致**——否则每个调用点都要重写，
 * 而"逐字保留"是这次移植的硬要求。这里用 `useSyncExternalStore` 实现同一个
 * selector 订阅语义：
 *
 *   const useFoo = createStore((set, get) => ({ ... }))
 *   useFoo((s) => s.bar)        // 订阅单个字段
 *   useFoo.getState()          // 组件外读取
 *   useFoo.setState(...)       // 组件外写入
 *   useFoo.use.bar()           // zustand v5 风格的选择器
 *
 * 这就是"用普通 React 状态替换 store"：状态本身仍然在 React 之外，但每个组件
 * 通过 useSyncExternalStore 订阅，没有第三方依赖。
 */
export function createStore(initializer) {
  let state;
  const listeners = new Set();

  const getState = () => state;
  const setState = (partial, replace) => {
    const next = typeof partial === "function" ? partial(state) : partial;
    if (!next) return;
    const merged = replace ? next : Object.assign({}, state, next);
    if (Object.is(merged, state)) return;
    state = merged;
    listeners.forEach((listener) => listener());
  };
  const subscribe = (listener) => {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  };

  state = initializer(setState, getState);

  function useStore(selector) {
    const select = selector ?? ((s) => s);
    return useSyncExternalStore(
      subscribe,
      () => select(getState()),
      () => select(getState()),
    );
  }

  useStore.getState = getState;
  useStore.setState = setState;
  useStore.subscribe = subscribe;
  // zustand v5 的 `use.X()` 取字段写法（InteractiveIframeHost 用到）。
  useStore.use = new Proxy(
    {},
    {
      get: (_target, key) => () => useStore((s) => s[key]),
    },
  );

  return useStore;
}
