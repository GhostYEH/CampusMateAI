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
