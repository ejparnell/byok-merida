import { spawnSync } from 'node:child_process'

const parseVersion = (value) =>
  value
    .match(/\d+\.\d+\.\d+/)?.[0]
    .split('.')
    .map(Number)

function versionAtLeast(actual, minimum) {
  for (let index = 0; index < minimum.length; index += 1) {
    if (actual[index] > minimum[index]) return true
    if (actual[index] < minimum[index]) return false
  }
  return true
}

function readVersion(command, args, label) {
  const result = spawnSync(command, args, {
    cwd: process.cwd(),
    encoding: 'utf8',
  })
  if (result.error || result.status !== 0) {
    console.error(`${label} is required for the final-app toolchain.`)
    process.exit(1)
  }
  const version = parseVersion(`${result.stdout} ${result.stderr}`)
  if (!version) {
    console.error(`${label} returned an unreadable version.`)
    process.exit(1)
  }
  return version
}

function requireMinimum(actual, minimum, label) {
  if (!versionAtLeast(actual, minimum)) {
    console.error(`${label} ${minimum.join('.')} or newer is required.`)
    process.exit(1)
  }
}

function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: process.cwd(),
    stdio: 'inherit',
  })
  if (result.error) {
    console.error(`${command} is required for the final-app toolchain.`)
    process.exit(1)
  }
  if (result.status !== 0) process.exit(result.status ?? 1)
}

requireMinimum(parseVersion(process.versions.node), [22, 18, 0], 'Node')
requireMinimum(readVersion('npm', ['--version'], 'npm'), [11, 11, 0], 'npm')
requireMinimum(readVersion('uv', ['--version'], 'uv'), [0, 11, 28], 'uv')

run('npm', ['ci'])
run('uv', [
  '--cache-dir',
  '.cache/uv',
  'sync',
  '--project',
  'apps/api',
  '--frozen',
])

const python = readVersion(
  'uv',
  [
    '--cache-dir',
    '.cache/uv',
    'run',
    '--project',
    'apps/api',
    'python',
    '--version',
  ],
  'Python',
)
if (python.join('.') !== '3.14.2') {
  console.error(
    'Python 3.14.2 is required for the preferred local environment.',
  )
  process.exit(1)
}
