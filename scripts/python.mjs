import { existsSync } from 'node:fs'
import { spawnSync } from 'node:child_process'

const args = process.argv.slice(2)
if (args.length === 0) {
  console.error('A Python command is required.')
  process.exit(2)
}

const uv = spawnSync('uv', ['--version'], { encoding: 'utf8' })
let command
let commandArgs

if (!uv.error && uv.status === 0) {
  command = 'uv'
  commandArgs = [
    '--cache-dir',
    '.cache/uv',
    'run',
    '--project',
    'apps/api',
    'python',
    ...args,
  ]
} else {
  const python =
    process.platform === 'win32'
      ? 'apps/api/.venv/Scripts/python.exe'
      : 'apps/api/.venv/bin/python'
  if (!existsSync(python)) {
    console.error(
      'The Merida Python environment is missing. Install uv, then run npm run setup.',
    )
    process.exit(1)
  }
  command = python
  commandArgs = args
}

const result = spawnSync(command, commandArgs, {
  cwd: process.cwd(),
  stdio: 'inherit',
})
if (result.error) {
  console.error(`Unable to start ${command}.`)
  process.exit(1)
}
process.exit(result.status ?? 1)
