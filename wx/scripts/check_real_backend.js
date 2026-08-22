const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const source = fs.readFileSync(path.join(root, 'miniprogram/services/repository.ts'), 'utf8')

assert.match(source, /mockMode:\s*false/, 'student app must default to real backend mode')
assert.match(
  source,
  /apiBaseUrl:\s*'http:\/\/192\.168\.1\.17:8000'/,
  'student app must default to the active LAN backend',
)
assert.match(source, /getConnectionState\(\)/, 'repository must expose the active connection state')
assert.match(source, /probeRealBackend\(\)/, 'repository must expose an explicit health probe')

console.log('PASS real backend defaults and connection contracts')
