#!/usr/bin/env node
'use strict'

const fs = require('fs')
const path = require('path')

const MINIPROGRAM_ROOT = path.join(__dirname, '..', 'miniprogram')
const APP_JSON = path.join(MINIPROGRAM_ROOT, 'app.json')

const MAIN_BUDGET_WARN = 1.5 * 1024 * 1024
const MAIN_BUDGET_ERROR = 1.8 * 1024 * 1024
const SUB_BUDGET_WARN = 1.5 * 1024 * 1024
const SUB_BUDGET_ERROR = 1.8 * 1024 * 1024

const IMAGE_EXTS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'])
const VIDEO_EXTS = new Set(['.mp4', '.mov', '.avi', '.webm'])
const MODEL_EXTS = new Set(['.tflite', '.onnx', '.pt', '.pth', '.h5', '.keras', '.bin', '.npy', '.npz', '.pkl'])
const STALE_EXTS = new Set(['.map', '.bak', '.backup', '.old', '.tmp', '.log', '.psd', '.fig', '.zip', '.rar', '.7z', '.csv', '.xlsx', '.docx'])

function walkDir(dir) {
  const results = []
  if (!fs.existsSync(dir)) return results
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === 'node_modules') continue
    const fullPath = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      results.push(...walkDir(fullPath))
    } else {
      const stat = fs.statSync(fullPath)
      results.push({
        absPath: fullPath,
        relPath: path.relative(MINIPROGRAM_ROOT, fullPath).replace(/\\/g, '/'),
        size: stat.size,
        ext: path.extname(entry.name).toLowerCase(),
      })
    }
  }
  return results
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

function sumBy(files, predicate) {
  return files.filter(predicate).reduce((acc, f) => acc + f.size, 0)
}

function main() {
  const allFiles = walkDir(MINIPROGRAM_ROOT)
  const filesystemTotal = allFiles.reduce((acc, f) => acc + f.size, 0)

  const appJson = JSON.parse(fs.readFileSync(APP_JSON, 'utf8'))
  const mainPages = appJson.pages || []
  const subPackages = appJson.subPackages || appJson.subpackages || []

  const subRoots = subPackages.map(s => s.root)

  const mainFiles = []
  const subFiles = {}
  for (const sub of subPackages) {
    subFiles[sub.root] = []
  }

  for (const f of allFiles) {
    let assigned = false
    for (const root of subRoots) {
      if (f.relPath.startsWith(root + '/')) {
        subFiles[root].push(f)
        assigned = true
        break
      }
    }
    if (!assigned) {
      mainFiles.push(f)
    }
  }

  const mainSize = mainFiles.reduce((acc, f) => acc + f.size, 0)
  const subSizes = {}
  let subTotal = 0
  let maxSubSize = 0
  for (const sub of subPackages) {
    const sz = subFiles[sub.root].reduce((acc, f) => acc + f.size, 0)
    subSizes[sub.root] = sz
    subTotal += sz
    maxSubSize = Math.max(maxSubSize, sz)
  }
  const assignedTotal = mainSize + subTotal
  const unassigned = filesystemTotal - assignedTotal

  console.log('='.repeat(60))
  console.log('  CampusMateAI 微信小程序包体积审计')
  console.log('  (文件系统估算值，非微信开发者工具构建结果)')
  console.log('='.repeat(60))
  console.log()

  console.log('【整体体积】')
  console.log(`  总文件数: ${allFiles.length}`)
  console.log(`  文件系统总计: ${formatBytes(filesystemTotal)}`)
  console.log()

  const byExt = {}
  for (const f of allFiles) {
    if (!byExt[f.ext]) byExt[f.ext] = { count: 0, size: 0 }
    byExt[f.ext].count++
    byExt[f.ext].size += f.size
  }
  console.log('【按类型统计 (全局)】')
  Object.entries(byExt)
    .sort((a, b) => b[1].size - a[1].size)
    .forEach(([ext, info]) => {
      console.log(`  ${(ext || '(无扩展名)').padEnd(12)}  ${String(info.count).padStart(4)} 个  ${formatBytes(info.size).padStart(12)}`)
    })
  console.log()

  const imagesSize = sumBy(allFiles, f => IMAGE_EXTS.has(f.ext))
  const svgSize = sumBy(allFiles, f => f.ext === '.svg')
  const videoSize = sumBy(allFiles, f => VIDEO_EXTS.has(f.ext))
  const modelSize = sumBy(allFiles, f => MODEL_EXTS.has(f.ext))
  const staleSize = sumBy(allFiles, f => STALE_EXTS.has(f.ext))

  console.log('【关键指标 (全局)】')
  console.log(`  图片 (png/jpg/...):  ${formatBytes(imagesSize)}`)
  console.log(`  SVG:                ${formatBytes(svgSize)}`)
  console.log(`  视频 (mp4/...):     ${formatBytes(videoSize)}`)
  console.log(`  模型文件:            ${formatBytes(modelSize)}`)
  console.log(`  潜在无用文件:        ${formatBytes(staleSize)}`)
  console.log()

  if (modelSize > 0) {
    console.log('  [P0] 检测到模型文件进入微信包！')
    allFiles.filter(f => MODEL_EXTS.has(f.ext)).forEach(f => {
      console.log(`    - ${f.relPath} (${formatBytes(f.size)})`)
    })
    console.log()
  }

  if (staleSize > 0) {
    console.log('  [警告] 检测到潜在无用文件:')
    allFiles.filter(f => STALE_EXTS.has(f.ext)).forEach(f => {
      console.log(`    - ${f.relPath} (${formatBytes(f.size)})`)
    })
    console.log()
  }

  console.log('【Top 30 最大文件】')
  console.log(`  ${'排名'.padStart(4)}  ${'大小'.padStart(12)}  ${'类型'.padStart(6)}  ${'归属'.padEnd(18)}  路径`)
  console.log(`  ${'-'.repeat(80)}`)
  const top30 = [...allFiles].sort((a, b) => b.size - a.size).slice(0, 30)
  top30.forEach((f, i) => {
    let owner = '主包'
    for (const root of subRoots) {
      if (f.relPath.startsWith(root + '/')) { owner = root; break }
    }
    console.log(`  ${String(i + 1).padStart(4)}  ${formatBytes(f.size).padStart(12)}  ${f.ext.padStart(6)}  ${owner.padEnd(18)}  ${f.relPath}`)
  })
  console.log()

  console.log('【主包页面】')
  mainPages.forEach(p => console.log(`  - ${p}`))
  console.log()

  const mainByExt = {}
  for (const f of mainFiles) {
    if (!mainByExt[f.ext]) mainByExt[f.ext] = 0
    mainByExt[f.ext] += f.size
  }
  console.log('【主包估算大小】')
  console.log(`  ${formatBytes(mainSize)}`)
  console.log(`  构成:`)
  Object.entries(mainByExt)
    .sort((a, b) => b[1] - a[1])
    .forEach(([ext, sz]) => {
      console.log(`    ${(ext || '(无扩展名)').padEnd(8)} ${formatBytes(sz).padStart(12)}  (${(sz / mainSize * 100).toFixed(1)}%)`)
    })
  if (mainSize > MAIN_BUDGET_ERROR) {
    console.log(`  [ERROR] 主包超过 ${formatBytes(MAIN_BUDGET_ERROR)} 内部预算！`)
  } else if (mainSize > MAIN_BUDGET_WARN) {
    console.log(`  [WARNING] 主包超过 ${formatBytes(MAIN_BUDGET_WARN)} 内部预算`)
  } else {
    console.log(`  [OK] 主包在 ${formatBytes(MAIN_BUDGET_WARN)} 内部预算内`)
  }
  console.log()

  console.log('【分包估算大小】')
  for (const sub of subPackages) {
    const sz = subSizes[sub.root]
    console.log(`  ${sub.root.padEnd(20)}  ${formatBytes(sz).padStart(12)}  (${sub.pages.length} 页面)`)
    sub.pages.forEach(p => console.log(`    - ${p}`))
    if (sz > SUB_BUDGET_ERROR) {
      console.log(`    [ERROR] 超过 ${formatBytes(SUB_BUDGET_ERROR)} 内部预算！`)
    } else if (sz > SUB_BUDGET_WARN) {
      console.log(`    [WARNING] 超过 ${formatBytes(SUB_BUDGET_WARN)} 内部预算`)
    }
  }
  console.log()

  console.log('【Package reconciliation】')
  console.log(`  filesystem total:  ${formatBytes(filesystemTotal)}`)
  console.log(`  main package:      ${formatBytes(mainSize)}`)
  console.log(`  subpackage total:  ${formatBytes(subTotal)}`)
  console.log(`  assigned total:    ${formatBytes(assignedTotal)}`)
  console.log(`  unassigned:        ${formatBytes(Math.abs(unassigned))}`)
  if (Math.abs(unassigned) > 100) {
    console.log(`  [ERROR] 包体积统计无法对账 (差值 > 100 B)`)
  } else {
    console.log(`  [OK] 对账一致，每个文件唯一归属一个包`)
  }
  console.log()

  console.log('【预算阈值】')
  console.log(`  主包 WARNING: ${formatBytes(MAIN_BUDGET_WARN)}  ERROR: ${formatBytes(MAIN_BUDGET_ERROR)}`)
  console.log(`  分包 WARNING: ${formatBytes(SUB_BUDGET_WARN)}  ERROR: ${formatBytes(SUB_BUDGET_ERROR)}`)
  console.log(`  (注: 项目内部预警值，非微信官方限制)`)
  console.log()

  console.log('='.repeat(60))
  const exitCode = (mainSize > MAIN_BUDGET_ERROR || maxSubSize > SUB_BUDGET_ERROR || Math.abs(unassigned) > 100) ? 1 : 0
  if (exitCode) {
    console.log('  [FAIL] 存在超过 ERROR 预算的包或对账失败')
  } else {
    console.log('  [PASS] 所有包在内部预算内且对账一致')
  }
  console.log('='.repeat(60))
  process.exit(exitCode)
}

main()
