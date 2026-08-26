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
const cpmState = loadTypeScript('miniprogram/services/cpm-counselor-state.ts')
const digitalHumanAudio = loadTypeScript('miniprogram/services/digital-human-audio.ts')

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

function testCpmConversationTransitions() {
  const initial = cpmState.createCpmState()
  assert.equal(cpmState.shouldShowCpmSuggestions(initial), true)
  assert.deepEqual(initial.recommendations.map((item) => item.id), ['freshman', 'graduate', 'club', 'balance'])

  const submitted = cpmState.submitCpmQuestion(initial, '  大一应该怎么规划？  ', 1000)
  assert.equal(submitted.sending, true)
  assert.equal(submitted.chatActive, true)
  assert.equal(submitted.input, '')
  assert.deepEqual(submitted.messages.map((item) => [item.role, item.status]), [
    ['user', 'COMPLETED'], ['assistant', 'GENERATING'],
  ])
  assert.equal(cpmState.shouldShowCpmSuggestions(submitted), false)

  const assistantId = submitted.messages[1].id
  const completed = cpmState.completeCpmAnswer(submitted, assistantId, '先建立稳定作息。')
  assert.equal(completed.sending, false)
  assert.equal(completed.speechText, '先建立稳定作息。')
  assert.equal(completed.speechRequestId, 1)
  assert.equal(completed.messages[1].status, 'COMPLETED')

  const failed = cpmState.failCpmAnswer(submitted, assistantId, '网络错误')
  assert.equal(failed.sending, false)
  assert.equal(failed.messages[1].status, 'ERROR')
  assert.match(failed.messages[1].text, /暂时无法生成回答/)
}

function testCpmRecommendationRotation() {
  const rotated = cpmState.shuffleCpmRecommendations(cpmState.createCpmState())
  assert.deepEqual(rotated.recommendations.map((item) => item.id), ['internship', 'direction', 'friendship', 'habits'])
  assert.deepEqual(cpmState.shuffleCpmRecommendations(rotated).recommendations.map((item) => item.id), ['freshman', 'graduate', 'club', 'balance'])
}

function testPcm16WavEnvelope() {
  const pcm = new Uint8Array([1, 2, 3, 4]).buffer
  const wav = digitalHumanAudio.pcm16ToWav(pcm, 24000, 1)
  const bytes = new Uint8Array(wav)
  const text = (start, length) => String.fromCharCode(...bytes.slice(start, start + length))
  const view = new DataView(wav)
  assert.equal(text(0, 4), 'RIFF')
  assert.equal(text(8, 4), 'WAVE')
  assert.equal(text(36, 4), 'data')
  assert.equal(view.getUint32(24, true), 24000)
  assert.equal(view.getUint32(40, true), 4)
  assert.deepEqual(Array.from(bytes.slice(44)), [1, 2, 3, 4])
  assert.equal(digitalHumanAudio.digitalHumanAvatarUrl('https://campus.example/api/v1/'), 'https://campus.example/digital-human/fallback-avatar.png')
}

testExpressionSignal()
testNotificationInbox()
testVisionPreprocessUsesAndroidNhwcContract()
testCpmConversationTransitions()
testCpmRecommendationRotation()
testPcm16WavEnvelope()
console.log('PASS domain services: expression signal, vision preprocessing, notification inbox, CPM state, and digital-human audio')
