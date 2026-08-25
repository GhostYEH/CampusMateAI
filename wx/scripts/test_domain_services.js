const assert = require('node:assert/strict')
const fs = require('node:fs')
const Module = require('node:module')
const path = require('node:path')
const ts = require('typescript')

const projectRoot = path.resolve(__dirname, '..')

function loadTypeScript(relativePath) {
  const filename = path.join(projectRoot, relativePath)
  const source = fs.readFileSync(filename, 'utf8')
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, strict: true },
    fileName: filename,
  }).outputText
  const loaded = new Module(filename, module)
  loaded.filename = filename
  loaded.paths = Module._nodeModulePaths(path.dirname(filename))
  loaded._compile(output, filename)
  return loaded.exports
}

const expression = loadTypeScript('miniprogram/services/expression-signal.ts')
const notifications = loadTypeScript('miniprogram/services/notification-inbox.ts')
const visionPreprocess = loadTypeScript('miniprogram/services/vision-preprocess.ts')

function testExpressionSignal() {
  const processor = new expression.ExpressionSignalProcessor(undefined, 3, 5_000, 'wx-test')
  assert.equal(processor.push({ label: 'happy', confidence: 0.4, timestamp: 1_000 }), undefined)
  assert.equal(processor.push({ label: 'happy', confidence: 0.5, timestamp: 1_100 }), undefined)
  const stable = processor.push({ label: 'happy', confidence: 0.6, timestamp: 1_200 })
  assert.equal(stable.label, 'happy')
  assert.equal(stable.isStable, true)
  assert.equal(stable.modelVersion, 'wx-test')
  assert.equal(processor.latest(6_200).label, 'happy')
  assert.equal(processor.latest(6_201), undefined)

  const strict = new expression.ExpressionSignalProcessor(undefined, 2, 5_000)
  assert.equal(strict.push({ label: 'sad', confidence: 0.67, timestamp: 2_000 }), undefined)
  assert.equal(strict.push({ label: 'NO_FACE', confidence: 1, timestamp: 2_100 }), undefined)
  assert.equal(strict.latest(2_100), undefined)

  const greeting = expression.greetingForExpression({
    label: 'fear', confidence: 0.9, isStable: true, timestamp: 4_000, modelVersion: 'test',
  }, 4_200)
  assert.match(greeting, /紧张/)
  assert.equal(expression.greetingForExpression({
    label: 'fear', confidence: 0.9, isStable: true, timestamp: 4_000, modelVersion: 'test',
  }, 9_001), undefined)
}

function testNotificationInbox() {
  assert.equal(notifications.classifyNotificationSource('企业微信：软件工程群', ''), 'wecom')
  assert.equal(notifications.classifyNotificationSource('学习通', '新作业已发布'), 'xuexitong')
  assert.equal(notifications.classifyNotificationSource('2026 新生班微信群', '请查收通知'), 'wechat')
  assert.equal(notifications.classifyNotificationSource('QQ', '课程群消息'), 'qq')
  assert.equal(notifications.classifyNotificationSource('教务处', '选课通知'), 'campus')

  const first = notifications.createInboxRecord('微信群', '选课通知', '请于周五完成选课', 1_000)
  const duplicate = notifications.createInboxRecord('微信群', ' 选课通知 ', '请于周五完成选课', 1_200)
  const second = notifications.createInboxRecord('学习通', '作业', '第一章作业', 2_000)
  const inserted = notifications.upsertInboxRecord([], first)
  assert.equal(notifications.upsertInboxRecord(inserted, duplicate).length, 1)
  const all = notifications.upsertInboxRecord(inserted, second)
  assert.deepEqual(notifications.filterInboxRecords(all, 'xuexitong', '').map((item) => item.id), [second.id])
  assert.deepEqual(notifications.filterInboxRecords(all, 'all', '选课').map((item) => item.id), [first.id])
  assert.deepEqual(notifications.removeInboxRecord(all, first.id).map((item) => item.id), [second.id])

  assert.deepEqual(notifications.addWhitelistGroup(['软件工程群'], ' 软件工程群 '), ['软件工程群'])
  assert.deepEqual(notifications.addWhitelistGroup(['软件工程群'], '2026 新生班'), ['软件工程群', '2026 新生班'])
}

function testVisionPreprocessUsesAndroidNhwcContract() {
  const rgba = new Uint8Array([
    255, 255, 255, 255,
    0, 0, 0, 255,
    128, 128, 128, 255,
    64, 64, 64, 255,
  ])
  const tensor = visionPreprocess.preprocessExpressionFrame(rgba.buffer, 2, 2, 2)
  assert.deepEqual(visionPreprocess.EXPRESSION_INPUT_SHAPE, [1, 96, 96, 3])
  assert.equal(tensor.length, 12)
  assert.ok(Math.abs(tensor[0] - ((1 - 0.485) / 0.229)) < 1e-6)
  assert.ok(Math.abs(tensor[1] - ((1 - 0.456) / 0.224)) < 1e-6)
  assert.ok(Math.abs(tensor[2] - ((1 - 0.406) / 0.225)) < 1e-6)
  assert.ok(Math.abs(tensor[3] - ((0 - 0.485) / 0.229)) < 1e-6)
}

testExpressionSignal()
testNotificationInbox()
testVisionPreprocessUsesAndroidNhwcContract()
console.log('PASS domain services: expression signal, vision preprocessing, and notification inbox')
