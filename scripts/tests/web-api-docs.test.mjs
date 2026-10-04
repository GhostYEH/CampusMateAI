import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';

const root = new URL('../../', import.meta.url);
const read = (path) => readFileSync(new URL(path, root), 'utf8');
const adapters = new Map(
  ['agentRuntimeApi', 'learnerStateApi'].map((name) => {
    const path = `webreact/src/data/${name}.js`;
    const source = read(path);
    const exports = new Map(
      [...source.matchAll(/export\s+(?:async\s+)?(?:function|const)\s+(\w+)/g)]
        .map((match) => [match[1], source.slice(0, match.index).split('\n').length]),
    );
    return [path, exports];
  }),
);

test('Web API documentation names existing adapters at their actual source lines', () => {
  for (const file of readdirSync(new URL('docs/api/', root)).filter((file) => file.endsWith('.md'))) {
    for (const line of read(`docs/api/${file}`).split('\n')) {
      if (line.startsWith('Web 封装：')) {
        for (const match of line.matchAll(/`(\w+)`（\[(webreact\/src\/data\/[^\]]+)\]/g)) {
          const exports = adapters.get(match[2]);
          if (exports) assert.ok(exports.has(match[1]), `${file}: missing ${match[2]} export ${match[1]}`);
        }
      }
      const row = line.match(/^\| \[(webreact\/src\/data\/[^:]+):(\d+)\].*? \| (\w+) \|/);
      if (row && adapters.has(row[1])) {
        assert.equal(adapters.get(row[1]).get(row[3]), Number(row[2]), `${file}: stale ${row[3]} source link`);
      }
    }
  }
});
