import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';

const root = new URL('../../', import.meta.url);
const read = (path) => readFileSync(new URL(path, root), 'utf8');
function adapterPaths(directory = 'webreact/src/data/') {
  return readdirSync(new URL(directory, root), { withFileTypes: true }).flatMap((entry) => {
    const path = `${directory}${entry.name}`;
    return entry.isDirectory() ? adapterPaths(`${path}/`) : entry.name.endsWith('.js') ? [path] : [];
  });
}
const adapters = new Map(
  adapterPaths().map((path) => {
    const source = read(path);
    const exports = new Map(
      [...source.matchAll(/export\s+(?:async\s+)?(?:function|const)\s+(\w+)/g)]
        .map((match) => [match[1], source.slice(0, match.index).split('\n').length]),
    );
    for (const match of source.matchAll(/export\s*\{([^}]+)\}(?:\s+from\s+['"][^'"]+['"])?/g)) {
      const line = source.slice(0, match.index).split('\n').length;
      for (const entry of match[1].split(',')) {
        const names = entry.trim().split(/\s+as\s+/);
        if (names[0]) exports.set(names.at(-1), line);
      }
    }
    // agentApi exposes callable object members as its documented adapter surface.
    if (path.endsWith('/agentApi.js')) {
      for (const match of source.matchAll(/^\s{2}(\w+):.*=>/gm)) {
        exports.set(match[1], source.slice(0, match.index).split('\n').length);
      }
    }
    return [path, exports];
  }),
);

test('Web API documentation names existing adapters at their actual source lines', () => {
  for (const file of readdirSync(new URL('docs/api/', root)).filter((file) => file.endsWith('.md'))) {
    for (const line of read(`docs/api/${file}`).split('\n')) {
      if (line.startsWith('Web 封装：')) {
        for (const match of line.matchAll(/`(\w+)`（\[(webreact\/src\/data\/[^\]]+)\]/g)) {
          const exports = adapters.get(match[2]);
          assert.ok(exports?.has(match[1]), `${file}: missing ${match[2]} export ${match[1]}`);
        }
      }
      const row = line.match(/^\| \[(webreact\/src\/data\/[^:]+):(\d+)\].*? \| (\w+) \|/);
      if (row) {
        assert.equal(adapters.get(row[1])?.get(row[3]), Number(row[2]), `${file}: stale ${row[3]} source link`);
      }
    }
  }
});
