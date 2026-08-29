export function formatUsdMicros(micros: number): string {
  const negative = micros < 0
  const absolute = Math.abs(Math.trunc(micros))
  const dollars = Math.trunc(absolute / 1_000_000)
  const fraction = String(absolute % 1_000_000).padStart(6, '0')
  const trimmed = fraction.replace(/0+$/, '').padEnd(2, '0')
  return `${negative ? '-' : ''}$${dollars}.${trimmed}`
}
