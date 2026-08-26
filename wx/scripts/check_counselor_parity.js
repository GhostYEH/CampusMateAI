const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const pageTs = fs.readFileSync(path.join(root, 'miniprogram/pages/counselor/counselor.ts'), 'utf8')
const pageWxml = fs.readFileSync(path.join(root, 'miniprogram/pages/counselor/counselor.wxml'), 'utf8')
const repository = fs.readFileSync(path.join(root, 'miniprogram/services/repository.ts'), 'utf8')
const localVision = fs.readFileSync(path.join(root, 'miniprogram/services/local-vision-session.ts'), 'utf8')

for (const behavior of ['enableVision', 'disableVision', 'retryLastMessage', 'shuffleSuggestions', 'toggleDigitalHumanMute', 'toggleDigitalHumanPause', 'replayDigitalHuman']) {
  assert.match(pageTs, new RegExp(`${behavior}\\s*\\(`), `missing counselor behavior ${behavior}`)
}
for (const surface of ['CPM', '数字人', '本机表情陪伴', '画面不上传', '换一批', '静音', '暂停', '重播', '重试', 'camera']) {
  assert.ok(pageWxml.includes(surface), `missing counselor surface ${surface}`)
}
assert.match(repository, /expression_signal:/, 'chat request must support optional expression signal')
assert.match(repository, /\.\.\.\(expressionSignal/, 'chat request must omit missing expression signal')
assert.match(repository, /synthesizeCpmSpeech\s*\(/, 'repository must expose authenticated CPM speech synthesis')
assert.match(pageTs, /digitalHumanAudio\?\.stop\(\)/, 'counselor must stop digital-human audio when hidden')
assert.match(localVision, /\^https:\\\/\\\//, 'model downloads must require HTTPS')
assert.match(localVision, /preparedModelUrl/, 'vision sessions must reuse an already prepared model')
assert.match(localVision, /!this\.active \|\| this\.session !== activeSession/, 'late inference results must be ignored after stop')
console.log('PASS counselor parity contracts')
