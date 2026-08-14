const fs = require('fs')
const path = require('path')
const ts = require('typescript')

const source = fs.readFileSync(path.resolve(__dirname, '../miniprogram/services/date-utils.ts'), 'utf8')
const javascript = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText
const runtimeModule = { exports: {} }
new Function('module', 'exports', 'require', javascript)(runtimeModule, runtimeModule.exports, require)
const { buildCurrentWeek, normalizeDeadline } = runtimeModule.exports

const reference = new Date(2026, 7, 13, 12, 0, 0)
const today = normalizeDeadline('今天 23:59', reference)
const tomorrow = normalizeDeadline('明天 08:30', reference)
const monthDay = normalizeDeadline('8月20日 18:00', reference)
const invalid = normalizeDeadline('以后有空再做', reference)
const week = buildCurrentWeek(reference)

const assertions = [
  ['today deadline parses', today === new Date(2026, 7, 13, 23, 59, 0).toISOString()],
  ['tomorrow deadline parses', tomorrow === new Date(2026, 7, 14, 8, 30, 0).toISOString()],
  ['month-day deadline parses', monthDay === new Date(2026, 7, 20, 18, 0, 0).toISOString()],
  ['invalid deadline is rejected', invalid === null],
  ['week has seven days', week.length === 7],
  ['reference day is active', week.filter((day) => day.active).length === 1
    && week.find((day) => day.active).date === 13],
]

const failed = assertions.filter(([, passed]) => !passed)
if (failed.length) {
  failed.forEach(([name]) => console.error(`FAIL ${name}`))
  process.exit(1)
}
console.log(`PASS ${assertions.length} date utility contracts`)
