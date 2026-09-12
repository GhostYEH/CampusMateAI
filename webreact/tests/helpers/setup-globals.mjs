/**
 * Must be imported FIRST in test files, before api.js is loaded.
 * Overrides globalThis.localStorage with a functional mock so that
 * api.js createClient() captures a working storage instance.
 */
const _store = new Map();
globalThis.localStorage = {
  getItem: (k) => _store.get(k) ?? null,
  setItem: (k, v) => _store.set(k, String(v)),
  removeItem: (k) => _store.delete(k),
  clear: () => _store.clear(),
};

if (!globalThis.location) {
  globalThis.location = { pathname: "/learning-state", href: "" };
}

export { _store };