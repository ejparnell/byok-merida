import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const includeBuilds = process.argv.includes('--include-builds')
const roots = [
  'packages/api-client/openapi.json',
  'packages/api-client/src/generated',
  'apps/web/src',
  'apps/extension/src',
  ...(includeBuilds ? ['apps/web/dist', 'apps/extension/dist'] : []),
]
const forbidden = [
  /\/api\/v1\/demo\/reset/i,
  /demo_not_active/i,
  /resetDemo/,
  /ResetDemoResponse/,
  /reset demo/i,
  /demo mode/i,
]

function filesAt(path) {
  if (!statSync(path).isDirectory()) return [path]
  return readdirSync(path).flatMap((entry) => filesAt(join(path, entry)))
}

const failures = roots.flatMap((root) =>
  filesAt(root)
    .filter((path) => !path.endsWith('.test.ts'))
    .flatMap((path) => {
      const content = readFileSync(path, 'utf8')
      return forbidden
        .filter((pattern) => pattern.test(content))
        .map((pattern) => `${path}: ${pattern}`)
    }),
)

if (failures.length) {
  console.error('Obsolete demo administration surface detected:')
  failures.forEach((failure) => console.error(`- ${failure}`))
  process.exit(1)
}

console.log(
  `No obsolete demo administration surface found${includeBuilds ? ' in source or browser builds' : ''}.`,
)
