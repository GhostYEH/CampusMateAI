/**
 * magicclass-brand.mjs 的自检门禁。
 *
 * 这套用例把"provenance 仍然成立"钉住：一旦有人手工改了 magicclass-app 里的文件
 * 而没走补丁脚本，或声明表在同步上游后失效，这里会立刻变红。
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { audit, verify, treePathFor, MANIFEST, BRAND, PKG } from '../magicclass-brand.mjs';
import { existsSync, readFileSync } from 'node:fs';

test('清单存在且非空，否则校验没有意义', () => {
  assert.equal(existsSync(MANIFEST), true, '缺少 third_party/magicclass/source-manifest.sha256');
  assert.ok(readFileSync(MANIFEST, 'utf8').trim().split('\n').length > 100);
});

test('品牌补丁已完整生效', () => {
  const problems = audit();
  assert.deepEqual(problems, [], `品牌补丁未生效：\n${problems.slice(0, 10).join('\n')}`);
  assert.equal(BRAND, 'magic class');
  assert.equal(PKG, 'magicclass');
});

test('逆向校验：没有未声明的偏离', () => {
  const result = verify();
  assert.deepEqual(
    result.problems,
    [],
    `发现未声明的偏离（要么走补丁脚本，要么在 DECLARED_DEVIATIONS 里写明理由）：\n`
      + result.problems.slice(0, 10).join('\n'),
  );
  // 还原后逐字节一致的文件数应当是绝大多数，否则说明补丁规则本身出了问题
  assert.ok(
    result.checked / result.total > 0.9,
    `还原一致率过低：${result.checked}/${result.total}`,
  );
});

test('声明表里没有已经失效的条目', () => {
  const result = verify();
  assert.deepEqual(
    result.unusedDeclarations,
    [],
    `以下声明已不再偏离，应从 DECLARED_DEVIATIONS 删除：\n${result.unusedDeclarations.join('\n')}`,
  );
});

test('已声明偏离都是有据可查的具体文件', () => {
  const result = verify();
  assert.ok(result.declared.length > 0, '声明表为空说明机制没接上');
  for (const line of result.declared) {
    const path = line.slice(line.lastIndexOf('：') + 1);
    // 声明表与清单都用上游路径，树里的落点要过一层技术改名映射
    const onDisk = new URL(`../../magicclass-app/${treePathFor(path)}`, import.meta.url);
    assert.equal(existsSync(onDisk), true, `声明的文件不存在：${path}（树里应为 ${treePathFor(path)}）`);
  }
});

test('render-service 必须按已发布名依赖第三方包', () => {
  // @openmaic/dsl 与 @openmaic/renderer 是 npm 上的第三方包（不是我们的 workspace 包）。
  // 改名成 @magicclass/* 会得到一个解析不了的安装：这两个名字在 npm registry 上都是 404。
  const base = new URL('../../magicclass-app/render-service/', import.meta.url);
  const pkg = JSON.parse(readFileSync(new URL('package.json', base), 'utf8'));
  for (const name of ['@openmaic/dsl', '@openmaic/renderer']) {
    assert.ok(pkg.dependencies?.[name], `render-service 必须按已发布名依赖 ${name}`);
  }
  for (const wrong of ['@magicclass/dsl', '@magicclass/renderer']) {
    assert.equal(pkg.dependencies?.[wrong], undefined, `render-service 不能依赖 ${wrong}（npm 上不存在）`);
  }
  // lockfile 里的 resolved URL 也必须指向真实存在的包
  const lock = readFileSync(new URL('package-lock.json', base), 'utf8');
  assert.equal(lock.includes('@magicclass/dsl'), false, 'package-lock.json 仍指向不存在的 @magicclass/dsl');
  assert.equal(lock.includes('@magicclass/renderer'), false, 'package-lock.json 仍指向不存在的 @magicclass/renderer');
  // 源码里的 import 同样要走已发布名
  for (const rel of ['src/main.ts', 'src/preview-renderer.ts', 'src/preview-validation.ts']) {
    const text = readFileSync(new URL(rel, base), 'utf8');
    assert.equal(/@magicclass\/(dsl|renderer)\b/.test(text), false, `${rel} 仍 import 不存在的包`);
  }
});
