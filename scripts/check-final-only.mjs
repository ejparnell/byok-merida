import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const legacyPaths = [
  '.scratch',
  '.venv',
  'app-data/demo',
  'apps/extension-prototype',
  'apps/web-prototype',
  'bownarrow.png',
  'export',
  'report',
  'src',
  'test/parity',
]

const failures = legacyPaths
  .filter((path) => existsSync(path))
  .map((path) => `legacy path still exists: ${path}`)

const packageJson = JSON.parse(readFileSync('package.json', 'utf8'))
const scripts = packageJson.scripts ?? {}
for (const name of Object.keys(scripts)) {
  if (name.startsWith('final:') || name.startsWith('prototype:')) {
    failures.push(`legacy lifecycle name remains: ${name}`)
  }
}

for (const [name, command] of Object.entries(scripts)) {
  if (
    /(?:^|\s)src\/(?:backend|features)|test\/parity|apps\/(?:web|extension)-prototype/.test(
      command,
    )
  ) {
    failures.push(`script ${name} still invokes legacy code`)
  }
}

const oldEnvironmentKeys = [
  'PORT',
  'FIT_RUNTIME_PORT',
  'FIT_RUNTIME_URL',
  'PYTHON_BIN',
  'DEBUG_CAPTURE',
  'DEBUG_ANALYSIS_CONTENT',
  'DEEPSEEK_MODEL',
  'LLM_INPUT_FORMAT',
]
const environmentTemplate = readFileSync('.env.example', 'utf8')
for (const key of oldEnvironmentKeys) {
  if (new RegExp(`^${key}=`, 'm').test(environmentTemplate)) {
    failures.push(`legacy or speculative environment key remains: ${key}`)
  }
}

function markdownFilesAt(path) {
  if (!existsSync(path)) return []
  if (!statSync(path).isDirectory()) return path.endsWith('.md') ? [path] : []
  return readdirSync(path).flatMap((entry) =>
    markdownFilesAt(join(path, entry)),
  )
}

const authorityFiles = [
  'README.md',
  'CONTEXT-MAP.md',
  ...markdownFilesAt('docs'),
]
const forbiddenAuthorityText = [
  /(?:^|[ (`])src\/backend\//m,
  /(?:^|[ (`])src\/features\//m,
  /test\/parity/,
  /apps\/(?:web|extension)-prototype/,
  /docs\/proposed-final-app/,
  /npm run final:/,
  /npm run test:final/,
  /frozen prototype/i,
  /proposed final[- ]app/i,
]
for (const path of authorityFiles) {
  const content = readFileSync(path, 'utf8')
  for (const pattern of forbiddenAuthorityText) {
    if (pattern.test(content)) failures.push(`${path} contains ${pattern}`)
  }
}

if (failures.length) {
  console.error('Final-only repository check failed:')
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log('Repository contains only the supported FastAPI/React application.')
