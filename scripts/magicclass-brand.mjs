#!/usr/bin/env node
/**
 * magic'class 品牌补丁 —— 可重放，可校验，不是一次性 sed。
 *
 * `openmaic-app/` 是上游 OpenMAIC v1.0.3 的原样副本（见 third_party/openmaic/NOTICE.md）。
 * 改名是一次**有意的偏离**，所以偏离必须写成脚本：将来同步上游新版本时原样重放，
 * 而不是靠人回忆当初改了哪几千处。
 *
 * 三种模式：
 *   apply    应用补丁（幂等）
 *   check    只报告补丁是否已生效，不写文件
 *   verify   把补丁**逆向**回去，逐文件比对 third_party/openmaic/source-manifest.sha256，
 *            证明"这份树 = 上游 v1.0.3 + 本文件定义的改动"，不需要重新下载上游
 *
 * 三层规则，以及刻意**不做**的部分：
 *   1. 展示层：用户看得见的品牌词 `OpenMAIC` → `magic'class`。逐条精确替换，不用通配；
 *      撇号按上下文转义（单引号字符串改成双引号、JSX 文本用表达式），所以不会写出
 *      `'magic'class'` 这种语法错误的代码。
 *   2. npm 身份：包名 `openmaic` → `magicclass`、scope `@openmaic/*` → `@magicclass/*`，
 *      并把 `packages/@openmaic/` 目录一起改名。
 *   3. 保留：`OPENMAIC_*` 环境变量、`X-OpenMAIC-*` 响应头、数据库/容器/MIME 等内部管道名、
 *      代码注释里的上游沿革、上游自带的 Markdown 文档、THU-MAIC 的 MIT LICENSE 与来源链接；
 *      以及 `render-service` 按已发布版本依赖的 `@openmaic/dsl`、`@openmaic/renderer`
 *      —— 那是 npm 上的第三方包，不是我们的 workspace 包，改了会装不上。
 */
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, readdirSync, renameSync, statSync, writeFileSync } from 'node:fs';
import { basename, dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = dirname(dirname(fileURLToPath(import.meta.url)));
export const APP = join(REPO, 'openmaic-app');
export const MANIFEST = join(REPO, 'third_party', 'openmaic', 'source-manifest.sha256');

export const BRAND = "magic'class";
export const PKG = 'magicclass';
const SCOPE_OLD = '@openmaic/';
const SCOPE_NEW = `@${PKG}/`;
const SCOPE_DIR_OLD = SCOPE_OLD.slice(0, -1);
const SCOPE_DIR_NEW = SCOPE_NEW.slice(0, -1);

/** 展示层：每条都是"上游文件里必须存在的确切文本"，缺失即视为上游文案变了（报错而不是静默跳过）。 */
export const DISPLAY_EDITS = [
  { file: 'app/layout.tsx', from: `  title: 'OpenMAIC',`, to: `  title: "${BRAND}",` },
  { file: 'app/page.tsx', from: `alt="OpenMAIC"`, to: `alt="${BRAND}"` },
  { file: 'app/page.tsx', from: `        OpenMAIC Open Source Project`, to: `        {"${BRAND} Open Source Project"}` },
  { file: 'components/access-code-modal.tsx', from: `                OpenMAIC`, to: `                {"${BRAND}"}` },
  { file: 'components/stage/scene-sidebar.tsx', from: `alt="OpenMAIC"`, to: `alt="${BRAND}"` },
  { file: 'components/scene-renderers/pbl/v2/workspace.tsx', from: `alt="OpenMAIC"`, to: `alt="${BRAND}"` },
  { file: 'lib/brand/brand-config.ts', from: `productName: 'OpenMAIC',`, to: `productName: "${BRAND}",` },
  { file: 'lib/brand/brand-config.ts', from: `shortName: 'OpenMAIC',`, to: `shortName: "${BRAND}",` },
  { file: 'lib/video-export/emit-hyperframes/index.ts', from: `— OpenMAIC video`, to: `— ${BRAND} video` },
  { file: 'lib/i18n/workbench.ts', from: `officialDownload: 'OpenMAIC official skill',`, to: `officialDownload: "${BRAND} official skill",` },
  { file: 'lib/i18n/workbench.ts', from: `officialDownload: 'OpenMAIC官方skill',`, to: `officialDownload: "${BRAND}官方skill",` },
  // 上游自带这条用例，断言的就是"这份构建的品牌身份"；改名后它必须跟着改，
  // 而且只能改在这里 —— 手工改会让 verify 认为这是补丁之外的偏离。
  { file: 'tests/lib/brand/brand-config.test.ts', from: `productName).toBe('OpenMAIC');`, to: `productName).toBe("${BRAND}");` },
  { file: 'tests/lib/brand/brand-config.test.ts', from: `shortName).toBe('OpenMAIC');`, to: `shortName).toBe("${BRAND}");` },
];

/** i18n 里品牌词是 JSON 字符串值，双引号包裹，撇号安全，可以按 token 整体替换。 */
export const I18N_DIRS = ['lib/i18n/locales', 'lib/i18n/workbench-locales'];
export const I18N_TOKENS = [['OpenMAIC', BRAND], ['MAIC Agent', `${BRAND} Agent`]];

const TEXT_EXT = new Set(['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.json', '.css', '.html', '.yaml', '.yml', '.toml']);
const TEXT_NAME = new Set(['Dockerfile', 'docker-compose.yml', 'pnpm-workspace.yaml', '.npmrc']);
const SKIP_DIRS = new Set(['node_modules', '.next', '.git', 'dist', 'out', 'coverage', 'build', '__pycache__', '.swc', '.turbo']);
/** 不参与 sweep 的子树：render-service 依赖 npm 上的已发布包，public/vendor 是构建产物。 */
const SKIP_PREFIX = ['render-service/', 'public/vendor/'];
/** 由工具链重新生成、内容合理地偏离上游的文件。 */
const GENERATED = ['pnpm-lock.yaml', 'public/vendor/', 'next-env.d.ts'];
/** 刻意没有入库的上游文件（见 docs/openmaic-deployment.md）。 */
const NOT_VENDORED = ['assets/', '.codegraph/.gitignore'];
/** 补丁之外我们自己加进这份树的文件。 */
const ADDED_BY_US = ['.env.example'];

/**
 * 我们自己界面里的可见品牌词（不属于上游偏离，所以 verify 不看这些文件）。
 * JSX 文本节点一律用表达式包裹，避免撇号撞上 react/no-unescaped-entities。
 */
export const OUR_EDITS = [
  {
    file: 'webreact/src/pages/LearningSpacePage.jsx',
    from: '上游 OpenMAIC 应用以独立进程运行，这里直接承载它完整的课堂、工作台与编辑器。',
    to: `${BRAND} 以独立进程运行，这里直接承载它完整的课堂、工作台与编辑器。`,
  },
  { file: 'webreact/src/components/AssignmentExplainPanel.jsx', from: 'title="OpenMAIC 作业讲解"', to: `title="${BRAND} 作业讲解"` },
  { file: 'webreact/src/components/AssignmentExplainPanel.jsx', from: 'title="让 OpenMAIC 讲解这份作业"', to: `title="让 ${BRAND} 讲解这份作业"` },
  { file: 'webreact/src/components/openmaic/OpenMAICClassroomStage.jsx', from: '>OpenMAIC</span>', to: `>{"${BRAND}"}</span>` },
  { file: 'webreact/src/components/openmaic/OpenMAICHome.jsx', from: 'aria-label="OpenMAIC 首页"', to: `aria-label="${BRAND} 首页"` },
  { file: 'webreact/src/components/openmaic/OpenMAICHome.jsx', from: '<strong>OpenMAIC</strong>', to: `<strong>{"${BRAND}"}</strong>` },
  { file: 'webreact/src/components/openmaic/OpenMAICHome.jsx', from: '>OpenMAIC Open Source Project</p>', to: `>{"${BRAND} Open Source Project"}</p>` },
  { file: 'webreact/src/pages/OpenMAICClassroomEntryPage.jsx', from: '<strong>OpenMAIC 正在准备课堂</strong>', to: `<strong>{"${BRAND}"} 正在准备课堂</strong>` },
];

function isText(file) {
  const name = basename(file);
  return TEXT_EXT.has(name.includes('.') ? `.${name.split('.').pop().toLowerCase()}` : '') || TEXT_NAME.has(name);
}

function inI18n(path) {
  return I18N_DIRS.some((dir) => path === dir || path.startsWith(`${dir}/`));
}

function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const st = statSync(full);
    const rel = relative(APP, full).split(sep).join('/');
    if (st.isDirectory()) {
      if (!SKIP_DIRS.has(entry) && !SKIP_PREFIX.some((p) => rel.startsWith(p)) ) walk(full, out);
    } else if (st.isFile() && isText(entry) && !SKIP_PREFIX.some((p) => rel.startsWith(p))) {
      out.push(full);
    }
  }
  return out;
}

function rel(file) {
  return relative(APP, file).split(sep).join('/');
}

/** package.json 只改"我们自己的包"：name 字段，以及指向 workspace 的依赖。 */
function rewritePackageJson(text, invert = false) {
  const [from, to] = invert ? [SCOPE_NEW, SCOPE_OLD] : [SCOPE_OLD, SCOPE_NEW];
  return text
    .split('\n')
    .map((line) => {
      if (/^\s*"name":\s*"(openmaic|magicclass)",?$/.test(line)) {
        return line.replace(invert ? `"${PKG}"` : '"openmaic"', invert ? '"openmaic"' : `"${PKG}"`);
      }
      if (/^\s*"name":\s*"@openmaic\//.test(line) || /^\s*"@openmaic\/[^"]+":\s*"workspace:/.test(line)
        || /^\s*"name":\s*"@magicclass\//.test(line) || /^\s*"@magicclass\/[^"]+":\s*"workspace:/.test(line)) {
        return line.split(from).join(to);
      }
      return line;
    })
    .join('\n');
}

/** i18n 的 token 替换；invert 时按相反顺序还原，保证与 apply 严格互逆。 */
function i18nReplace(text, invert) {
  let out = text;
  const ordered = invert ? [...I18N_TOKENS].reverse() : I18N_TOKENS;
  for (const [from, to] of ordered) out = out.split(invert ? to : from).join(invert ? from : to);
  return out;
}

function applyDisplayEdits(dryRun) {
  const changes = [];
  const problems = [];
  for (const edit of DISPLAY_EDITS) {
    const file = join(APP, edit.file);
    if (!existsSync(file)) {
      problems.push(`缺少文件：${edit.file}`);
      continue;
    }
    const text = readFileSync(file, 'utf8');
    if (text.includes(edit.to) && !text.includes(edit.from)) continue; // 已应用
    if (!text.includes(edit.from)) {
      problems.push(`${edit.file} 里找不到预期文本，上游文案可能已变：${JSON.stringify(edit.from.trim().slice(0, 50))}`);
      continue;
    }
    changes.push(`${edit.file}: ${JSON.stringify(edit.from.trim().slice(0, 34))} -> ${JSON.stringify(edit.to.trim().slice(0, 34))}`);
    if (!dryRun) writeFileSync(file, text.split(edit.from).join(edit.to), 'utf8');
  }
  return { changes, problems };
}

function applyOurEdits(dryRun) {
  const changes = [];
  const problems = [];
  for (const edit of OUR_EDITS) {
    const file = join(REPO, edit.file.split('/').join(sep));
    if (!existsSync(file)) {
      problems.push(`缺少文件：${edit.file}`);
      continue;
    }
    const text = readFileSync(file, 'utf8');
    if (!text.includes(edit.from)) {
      if (text.includes(edit.to)) continue;
      problems.push(`${edit.file} 里找不到预期文案：${JSON.stringify(edit.from.slice(0, 30))}`);
      continue;
    }
    changes.push(edit.file);
    if (!dryRun) writeFileSync(file, text.split(edit.from).join(edit.to), 'utf8');
  }
  return { changes, problems };
}

function applyI18n(dryRun) {
  const changes = [];
  const problems = [];
  for (const dir of I18N_DIRS) {
    const abs = join(APP, dir);
    if (!existsSync(abs)) {
      problems.push(`缺少 i18n 目录：${dir}`);
      continue;
    }
    for (const entry of readdirSync(abs)) {
      if (!entry.endsWith('.json')) continue;
      const file = join(abs, entry);
      const text = readFileSync(file, 'utf8');
      const next = i18nReplace(text, false);
      if (next !== text) {
        changes.push(`${dir}/${entry}`);
        if (!dryRun) writeFileSync(file, next, 'utf8');
      }
    }
  }
  return { changes, problems };
}

function applyScope(dryRun) {
  const changes = [];
  for (const file of walk(APP)) {
    const text = readFileSync(file, 'utf8');
    const path = rel(file);
    if (!text.includes(SCOPE_OLD) && !/"name":\s*"openmaic"/.test(text)) continue;
    const next = path.endsWith('package.json')
      ? rewritePackageJson(text.split(SCOPE_OLD).join(SCOPE_NEW), false)
      : text.split(SCOPE_OLD).join(SCOPE_NEW);
    if (next !== text) {
      changes.push(path);
      if (!dryRun) writeFileSync(file, next, 'utf8');
    }
  }
  const oldDir = join(APP, 'packages', SCOPE_DIR_OLD);
  const newDir = join(APP, 'packages', SCOPE_DIR_NEW);
  if (existsSync(oldDir) && !existsSync(newDir)) {
    changes.push(`${rel(oldDir)}/ -> ${rel(newDir)}/`);
    if (!dryRun) renameSync(oldDir, newDir);
  }
  return { changes };
}

/** 补丁是否已完整生效。 */
export function audit() {
  const problems = [];
  for (const edit of OUR_EDITS) {
    const file = join(REPO, edit.file.split('/').join(sep));
    if (existsSync(file) && readFileSync(file, 'utf8').includes(edit.from)) {
      problems.push(`(本站) ${edit.file} 仍有旧品牌词：${JSON.stringify(edit.from.slice(0, 26))}`);
    }
  }
  for (const edit of DISPLAY_EDITS) {
    const file = join(APP, edit.file);
    if (!existsSync(file)) continue;
    const text = readFileSync(file, 'utf8');
    if (text.includes(edit.from)) problems.push(`${edit.file} 仍有上游品牌词：${JSON.stringify(edit.from.trim().slice(0, 34))}`);
  }
  for (const dir of I18N_DIRS) {
    const abs = join(APP, dir);
    if (!existsSync(abs)) continue;
    for (const entry of readdirSync(abs)) {
      if (!entry.endsWith('.json')) continue;
      const text = readFileSync(join(abs, entry), 'utf8');
      if (text.includes('OpenMAIC') || text.includes('MAIC Agent')) problems.push(`${dir}/${entry} 仍有可见品牌词`);
    }
  }
  for (const file of walk(APP)) {
    const text = readFileSync(file, 'utf8');
    if (!text.includes(SCOPE_OLD)) continue;
    const path = rel(file);
    const keptPublished = path.endsWith('package.json') && /"@openmaic\/(dsl|renderer)":\s*"[^w"]/.test(text);
    const nameField = /^\s*"name":\s*"@openmaic\//m.test(text);
    if (!keptPublished && !nameField) problems.push(`${path} 仍有 ${SCOPE_OLD}`);
    if (keptPublished && nameField) problems.push(`${path} 的 name 仍未改名`);
  }
  if (existsSync(join(APP, 'packages', SCOPE_DIR_OLD))) problems.push(`packages/${SCOPE_DIR_OLD}/ 目录仍未改名`);
  const rootManifest = join(APP, 'package.json');
  if (existsSync(rootManifest) && /"name":\s*"openmaic"/.test(readFileSync(rootManifest, 'utf8'))) {
    problems.push('根 package.json 的 name 仍是 openmaic');
  }
  return problems;
}

function treePathFor(upstreamPath) {
  return upstreamPath.startsWith(`packages/${SCOPE_OLD}`)
    ? upstreamPath.replace(`packages/${SCOPE_OLD}`, `packages/${SCOPE_NEW}`)
    : upstreamPath;
}

/** 目录改名前后都能定位：补丁未打时上游路径就是树里的路径。 */
function locate(upstreamPath) {
  for (const candidate of [treePathFor(upstreamPath), upstreamPath]) {
    const file = join(APP, candidate.split('/').join(sep));
    if (existsSync(file)) return file;
  }
  return null;
}

function startsWithAny(path, list) {
  return list.some((prefix) => path === prefix || path.startsWith(prefix));
}

/**
 * 逆向校验：把树里的内容按补丁规则**反向**还原，再和上游清单比哈希。
 * 通过即说明这份树除了本文件定义的改动，与上游 v1.0.3 逐字节一致。
 */
export function verify() {
  if (!existsSync(MANIFEST)) return { problems: ['找不到 third_party/openmaic/source-manifest.sha256'], checked: 0, regenerated: 0, absent: 0 };
  const entries = readFileSync(MANIFEST, 'utf8')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const i = line.indexOf('  ');
      return { sha: line.slice(0, i), path: line.slice(i + 2).replace(/^\.\//, '') };
    });
  const known = new Set(entries.map((e) => e.path));
  const problems = [];
  let checked = 0;
  let regenerated = 0;
  let absent = 0;
  for (const entry of entries) {
    if (startsWithAny(entry.path, NOT_VENDORED)) {
      absent += 1;
      continue;
    }
    if (startsWithAny(entry.path, GENERATED)) {
      regenerated += 1;
      continue;
    }
    const treeFile = locate(entry.path);
    if (!treeFile) {
      problems.push(`缺少上游文件：${entry.path}`);
      continue;
    }
    const raw = readFileSync(treeFile);
    const bytes = isText(entry.path) ? Buffer.from(restore(entry.path, raw.toString('utf8')), 'utf8') : raw;
    if (createHash('sha256').update(bytes).digest('hex') === entry.sha) checked += 1;
    else problems.push(`还原后仍与上游不符（品牌补丁之外的改动）：${entry.path}`);
  }
  const upstreamOf = (path) => path.replace(`packages/${SCOPE_NEW}`, `packages/${SCOPE_OLD}`);
  const extra = walk(APP)
    .map(rel)
    .map(upstreamOf)
    .filter((path) => !known.has(path) && !startsWithAny(path, ADDED_BY_US) && !startsWithAny(path, GENERATED));
  for (const path of extra) problems.push(`清单里没有的新文件（不是上游内容）：${path}`);
  return { checked, regenerated, absent, total: entries.length, problems };
}

/** verify 用的逆变换：与 apply 严格互逆。 */
function restore(path, text) {
  let out = text;
  if (inI18n(path) && path.endsWith('.json')) {
    out = i18nReplace(out, true);
  } else {
    for (const edit of [...DISPLAY_EDITS].reverse()) if (edit.file === path) out = out.split(edit.to).join(edit.from);
  }
  if (path.endsWith('package.json')) out = rewritePackageJson(out, true);
  return out.split(SCOPE_NEW).join(SCOPE_OLD);
}

function main(argv) {
  const mode = argv[2];
  if (!['apply', 'check', 'verify'].includes(mode)) {
    console.error('用法：node scripts/magicclass-brand.mjs <apply|check|verify>');
    return 2;
  }
  if (mode === 'verify') {
    const result = verify();
    console.log(`逆向校验：${result.checked}/${result.total} 个上游文件还原后逐字节一致`
      + `（工具链重新生成 ${result.regenerated}、刻意未入库 ${result.absent}）`);
    if (result.problems.length === 0) {
      console.log('结论：这份树 = 上游 OpenMAIC v1.0.3 + magicclass-brand.mjs 定义的改动');
      return 0;
    }
    console.error(`发现 ${result.problems.length} 处无法用品牌补丁解释的差异：`);
    for (const line of result.problems.slice(0, 30)) console.error(`  - ${line}`);
    return 1;
  }
  if (mode === 'check') {
    const problems = audit();
    if (problems.length === 0) {
      console.log(`品牌补丁已生效：展示层与 npm 身份均已是 ${BRAND} / ${PKG}`);
      return 0;
    }
    console.error(`品牌补丁不完整（${problems.length} 项）：`);
    for (const line of problems.slice(0, 30)) console.error(`  - ${line}`);
    return 1;
  }
  const steps = [applyDisplayEdits(false), applyOurEdits(false), applyI18n(false), applyScope(false)];
  const changed = steps.flatMap((s) => s.changes);
  const problems = steps.flatMap((s) => s.problems || []);
  console.log(`已应用 ${changed.length} 处改动：`);
  for (const line of changed.slice(0, 30)) console.log(`  * ${line}`);
  if (changed.length > 30) console.log(`  …另外 ${changed.length - 30} 处`);
  if (problems.length) {
    console.error(`需要人工确认（${problems.length} 项）：`);
    for (const line of problems.slice(0, 20)) console.error(`  ! ${line}`);
    return 1;
  }
  const remaining = audit();
  console.log(`补丁自检：${remaining.length === 0 ? '通过' : `仍有 ${remaining.length} 项未覆盖`}`);
  for (const line of remaining.slice(0, 10)) console.log(`  - ${line}`);
  return remaining.length === 0 ? 0 : 1;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = main(process.argv);
}
