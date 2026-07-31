import { mkdir, writeFile } from 'node:fs/promises'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { dirname, join, resolve } from 'node:path'
import { createSSRApp, h } from '../../web/node_modules/vue/dist/vue.esm-bundler.js'
import { renderToString } from '../../web/node_modules/@vue/server-renderer/dist/server-renderer.esm-bundler.js'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const repositoryRoot = resolve(scriptDir, '..', '..')
const iconPackage = join(
  repositoryRoot,
  'web',
  'node_modules',
  '@phosphor-icons',
  'vue',
  'dist',
  'icons',
)
const outputDir = join(repositoryRoot, 'wx', 'miniprogram', 'assets', 'icons')

const staticIcons = [
  ['quick-calendar', 'PhCalendarDots', 'fill', '#FFFFFF'],
  ['quick-task', 'PhCheckCircle', 'fill', '#FFFFFF'],
  ['quick-notice', 'PhBell', 'fill', '#FFFFFF'],
  ['quick-study', 'PhCalendarCheck', 'fill', '#FFFFFF'],
  ['quick-counselor', 'PhRobot', 'fill', '#FFFFFF'],
  ['arrow-right', 'PhArrowRight', 'bold', '#FFFFFF'],
  ['eye-light', 'PhEye', 'fill', '#667B89'],
  ['eye-dark', 'PhEye', 'fill', '#A8BAC4'],
  ['clock-white', 'PhClock', 'fill', '#FFFFFF'],
  ['pin-white', 'PhMapPin', 'fill', '#FFFFFF'],
  ['deadline-blue', 'PhBookOpen', 'fill', '#477BFF'],
  ['deadline-orange', 'PhBookOpen', 'fill', '#FFA23A'],
]

const tabIcons = [
  ['home', 'PhHouse'],
  ['courses', 'PhBookOpen'],
  ['tasks', 'PhCheckCircle'],
  ['counselor', 'PhRobot'],
  ['profile', 'PhUser'],
]

const variants = [
  ...staticIcons,
  ...tabIcons.flatMap(([name, component]) => [
    [`tab-${name}-inactive-light`, component, 'fill', '#667B89'],
    [`tab-${name}-active-light`, component, 'fill', '#2D6C92'],
    [`tab-${name}-inactive-dark`, component, 'fill', '#A8BAC4'],
    [`tab-${name}-active-dark`, component, 'fill', '#8AC1DF'],
  ]),
]

await mkdir(outputDir, { recursive: true })

for (const [filename, componentName, weight, color] of variants) {
  const moduleUrl = pathToFileURL(join(iconPackage, `${componentName}.vue.mjs`)).href
  const { default: Icon } = await import(moduleUrl)
  const app = createSSRApp({
    render: () => h(Icon, {
      size: 64,
      weight,
      color,
      'aria-hidden': 'true',
    }),
  })
  const svg = await renderToString(app)
  await writeFile(join(outputDir, `${filename}.svg`), `${svg}\n`, 'utf8')
}

process.stdout.write(`Generated ${variants.length} Phosphor SVG assets in ${outputDir}\n`)
