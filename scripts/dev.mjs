import { spawn, spawnSync } from 'node:child_process'

const clientBuild = spawnSync('npm', ['run', 'client'], {
  cwd: process.cwd(),
  stdio: 'inherit',
})
if (clientBuild.status !== 0) process.exit(clientBuild.status ?? 1)

const commands = [
  ['api', ['run', 'dev:api']],
  ['web', ['run', 'dev', '--workspace', '@merida/web']],
]

const children = commands.map(([name, args]) => {
  const child = spawn('npm', args, {
    cwd: process.cwd(),
    stdio: ['inherit', 'pipe', 'pipe'],
  })
  const forward = (stream, target) =>
    stream.on('data', (chunk) => {
      for (const line of chunk.toString().split(/(?<=\n)/)) {
        if (line) target.write(`[${name}] ${line}`)
      }
    })
  forward(child.stdout, process.stdout)
  forward(child.stderr, process.stderr)
  return child
})

let stopping = false
function stop(signal = 'SIGTERM') {
  if (stopping) return
  stopping = true
  for (const child of children) child.kill(signal)
}

for (const signal of ['SIGINT', 'SIGTERM'])
  process.on(signal, () => stop(signal))
for (const child of children) {
  child.on('exit', (code, signal) => {
    stop()
    if (signal) process.kill(process.pid, signal)
    else process.exitCode = code ?? 1
  })
}
