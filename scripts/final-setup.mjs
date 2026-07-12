import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'

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
run('npm', ['ci'])

const localPython =
  process.platform === 'win32'
    ? 'apps/api/.venv/Scripts/python.exe'
    : 'apps/api/.venv/bin/python'
const uvProbe = spawnSync('uv', ['--version'], { encoding: 'utf8' })
if (!uvProbe.error && uvProbe.status === 0) {
  requireMinimum(
    parseVersion(`${uvProbe.stdout} ${uvProbe.stderr}`),
    [0, 11, 28],
    'uv',
  )
  run('uv', [
    '--cache-dir',
    '.cache/uv',
    'sync',
    '--project',
    'apps/api',
    '--frozen',
    '--python',
    '3.14.2',
  ])
} else if (
  !existsSync(localPython) ||
  spawnSync(
    localPython,
    ['-c', 'import fastapi, langgraph, merida_api, pytest, uvicorn'],
    { cwd: process.cwd() },
  ).status !== 0
) {
  console.error(
    'uv 0.11.28 or newer is required for a clean setup. Install uv, then rerun npm run final:setup.',
  )
  process.exit(1)
} else {
  console.log(
    'Using the existing apps/api/.venv environment because uv is unavailable.',
  )
}

const python = existsSync(localPython)
  ? readVersion(localPython, ['--version'], 'Python')
  : readVersion(
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
