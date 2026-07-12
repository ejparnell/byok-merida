import type { ReactNode } from 'react'

export function cx(
  ...values: Array<string | false | null | undefined>
): string {
  return values.filter(Boolean).join(' ')
}

export function Spinner() {
  return <span className="spinner" aria-hidden="true" />
}

export function StatusDot({ status }: { status?: string }) {
  return (
    <span
      className={cx('status-dot', `is-${status ?? 'unknown'}`)}
      aria-hidden="true"
    />
  )
}

export function StatusBadge({
  status,
  children,
}: {
  status: string
  children?: ReactNode
}) {
  return (
    <span className={cx('status-badge', `is-${status}`)}>
      <StatusDot status={status} />
      {children ?? status}
    </span>
  )
}
