import { spawnSync } from 'node:child_process'

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

run('npm', ['ci'])
run('uv', [
  '--cache-dir',
  '.cache/uv',
  'sync',
  '--project',
  'apps/api',
  '--frozen',
])
