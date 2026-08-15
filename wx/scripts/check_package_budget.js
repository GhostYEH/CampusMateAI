const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..', 'miniprogram')
const maximumBytes = 2 * 1024 * 1024

function directoryBytes(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).reduce((total, entry) => {
    const fullPath = path.join(directory, entry.name)
    return total + (entry.isDirectory() ? directoryBytes(fullPath) : fs.statSync(fullPath).size)
  }, 0)
}

const sourceBytes = directoryBytes(root)
assert.ok(
  sourceBytes < maximumBytes,
  `raw mini program source is ${(sourceBytes / 1024).toFixed(1)}KB; expected less than 2048KB`,
)

console.log(`PASS package budget ${(sourceBytes / 1024).toFixed(1)}KB / 2048KB`)
