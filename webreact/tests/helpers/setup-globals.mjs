/**
 * Must be imported FIRST in test files, before api.js is loaded.
 * Overrides globalThis.localStorage with a functional mock so that
 * api.js createClient() captures a working storage instance.
 *
 * 注意：必须实现**完整的** Storage 接口（含 `length` 与 `key(i)`）。
 * 只实现 getItem/setItem/removeItem 的"半成品" mock 会让按前缀清理
 * （如 `purgeOtherIdentityJobs`）在测试里静默失效，从而掩盖真实缺陷。
 */
const _store = new Map();
globalThis.localStorage = {
  get length() {
    return _store.size;
  },
  key: (index) => Array.from(_store.keys())[index] ?? null,
  getItem: (k) => _store.get(k) ?? null,
  setItem: (k, v) => _store.set(k, String(v)),
  removeItem: (k) => _store.delete(k),
  clear: () => _store.clear(),
};

if (!globalThis.location) {
  globalThis.location = { pathname: "/learning-state", href: "" };
}

export { _store };