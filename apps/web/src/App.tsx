import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { cx, Spinner, StatusBadge, StatusDot } from '@merida/ui'
import type {
  CreateResumeResponse,
  RunApplicationAnalysisResponse,
} from '@merida/api-client'

import { createDashboardSession } from './features/dashboard/dashboardSession.ts'
import type {
  DashboardSession,
  DashboardState,
} from './features/dashboard/dashboardSession.ts'
import { createDashboardClient } from './shared/api/dashboardClient.ts'

function Brand() {
  return (
    <div className="brand" aria-label="Merida">
      <span className="brand-mark">M</span>
      <strong>Merida</strong>
    </div>
  )
}

function ArrowIcon() {
  return <span aria-hidden="true">↗</span>
}

function Section({
  eyebrow,
  title,
  meta,
  status,
  children,
}: {
  eyebrow: string
  title: string
  meta: string
  status: string
  children: ReactNode
}) {
  return (
    <section className="section-panel">
      <header className="section-header">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h2>{title}</h2>
        </div>
        <div className="section-meta">
          {meta && <span>{meta}</span>}
          <StatusBadge status={status}>
            {status === 'ready' ? 'Ready' : 'Blocked'}
          </StatusBadge>
        </div>
      </header>
      {children}
    </section>
  )
}

function Readiness({
  health,
  settings,
}: Pick<DashboardState, 'health' | 'settings'>) {
  const segments = [
    ['Settings', health?.checks?.settings],
    ['Notion', health?.checks?.notion],
    ['Analysis', health?.checks?.analysis],
    ['Resumes', health?.checks?.resumes],
    ['Ready', health?.status],
  ]
  return (
    <section className="readiness-card">
      <div className="readiness-heading">
        <div>
          <span className="eyebrow">Local workflow</span>
          <h1>Workflow overview</h1>
          <p>
            Run evidence-backed application work. Manage durable records in
            Notion.
          </p>
        </div>
      </div>
      <div className="status-track" aria-label="Workflow readiness">
        {segments.map(([label, status]) => (
          <div
            key={label}
            className={cx('status-segment', `is-${status || 'unknown'}`)}
          >
            <span>{label}</span>
            <strong>
              {status === 'ready'
                ? 'Ready'
                : status === 'blocked'
                  ? 'Blocked'
                  : 'Checking'}
            </strong>
          </div>
        ))}
      </div>
      <div className="model-grid">
        <div className="model-card">
          <span>Analysis model</span>
          <strong>{settings?.models?.analysis || '—'}</strong>
          <small>Read-only backend configuration</small>
        </div>
        <div className="model-card">
          <span>Resume model</span>
          <strong>{settings?.models?.resumes || '—'}</strong>
          <small>Read-only backend configuration</small>
        </div>
        <div className="provider-card">
          <span>Providers</span>
          <div>
            <StatusDot
              status={settings?.configured?.notion ? 'ready' : 'blocked'}
            />{' '}
            Notion
          </div>
          <div>
            <StatusDot
              status={settings?.configured?.deepseek ? 'ready' : 'blocked'}
            />{' '}
            DeepSeek
          </div>
        </div>
      </div>
      {Boolean(health?.errors.length) && (
        <ErrorCallout errors={health?.errors} />
      )}
    </section>
  )
}

function ErrorCallout({ errors }: { errors?: string[] }) {
  if (!errors?.length) return null
  return (
    <div className="error-callout" role="alert">
      {errors.map((error: string) => (
        <p key={error}>{error}</p>
      ))}
    </div>
  )
}

function EmptyState({ kind }: { kind: 'Applications' | 'Resumes' }) {
  return (
    <div className="empty-state">
      <span>Queue clear</span>
      <strong>No eligible {kind}</strong>
      <p>
        {kind === 'Applications'
          ? 'Capture or update Applications in Notion to prepare more analysis work.'
          : 'Run Application Analysis or review existing records in Notion.'}
      </p>
    </div>
  )
}

function QueueIdentity({
  item,
}: {
  item: { companyName: string; role: string }
}) {
  return (
    <div className="queue-identity">
      <span className="company-avatar">
        {item.companyName.slice(0, 2).toUpperCase()}
      </span>
      <span>
        <strong>{item.role}</strong>
        <small>{item.companyName}</small>
      </span>
    </div>
  )
}

function QueuePagination({
  pagination,
  currentCursor,
  onFirst,
  onNext,
  disabled,
}: {
  pagination?: { hasMore: boolean; nextCursor: string | null }
  currentCursor: string | null
  onFirst: () => void
  onNext: () => void
  disabled: boolean
}) {
  if (!pagination?.hasMore && !currentCursor && !disabled) return null
  return (
    <div className="pagination">
      <button type="button" onClick={onFirst} disabled={disabled}>
        First page
      </button>
      <button
        type="button"
        onClick={onNext}
        disabled={disabled || !pagination?.hasMore}
      >
        Next page <span aria-hidden="true">→</span>
      </button>
    </div>
  )
}

function AnalysisResult({
  result,
  onDismiss,
}: {
  result: RunApplicationAnalysisResponse | null
  onDismiss: () => void
}) {
  if (!result) return null
  return (
    <div
      className={cx('result-panel', result.ok ? 'is-success' : 'is-failure')}
      role="status"
    >
      <button
        className="dismiss-button"
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss Analysis result"
      >
        ×
      </button>
      <div>
        <span className="eyebrow">Latest result</span>
        <strong>{result.ok ? 'Analysis complete' : 'Analysis blocked'}</strong>
        <p>
          {result.processed || 0} processed · {result.succeeded || 0} analyzed ·{' '}
          {result.failed || 0} failed · {result.repaired || 0} repaired
        </p>
      </div>
      {result.items?.length > 0 && (
        <ul>
          {result.items.map((item) => (
            <li key={item.applicationId}>
              <span>
                {item.role} at {item.companyName}
              </span>
              <b>
                {item.result}
                {item.matchScore != null ? ` · ${item.matchScore}%` : ''}
              </b>
              {'errors' in item && item.errors?.length > 0 && (
                <small>{item.errors.join(' ')}</small>
              )}
            </li>
          ))}
        </ul>
      )}
      <ErrorCallout errors={result.errors} />
      <ErrorCallout
        errors={result.validationFailures?.map((failure) => failure.message)}
      />
    </div>
  )
}

function AnalysisSection({
  state,
  session,
  batchLimit,
  setBatchLimit,
}: {
  state: DashboardState
  session: DashboardSession
  batchLimit: number
  setBatchLimit: (value: number) => void
}) {
  const queue = state.analysisQueue
  const ready = state.health?.checks?.analysis === 'ready'
  const runDisabled = !ready || !queue?.queueCount || state.analysisRunning
  return (
    <Section
      eyebrow="01 · Enrich"
      title="Application Analysis"
      meta={`${queue?.queueCount ?? '—'} waiting`}
      status={ready ? 'ready' : 'blocked'}
    >
      <div className="section-description">
        <p>
          Analyze the backend’s next eligible Applications. This list is a
          preview, not a selection.
        </p>
        <div className="analysis-controls">
          <label>
            <span>Batch limit</span>
            <input
              type="number"
              min="1"
              max="10"
              value={batchLimit}
              onChange={(event) => setBatchLimit(Number(event.target.value))}
            />
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={runDisabled}
            onClick={() => session.runAnalysis(batchLimit)}
          >
            {state.analysisRunning ? (
              <>
                <Spinner /> Running analysis
              </>
            ) : (
              <>
                Run analysis <span aria-hidden="true">→</span>
              </>
            )}
          </button>
        </div>
      </div>
      <div className={cx('queue-table', state.analysisRunning && 'is-muted')}>
        <div className="queue-head">
          <span>Eligible Application</span>
          <span>Status</span>
        </div>
        {queue?.items?.map((item) => (
          <div className="queue-row" key={item.applicationId}>
            <QueueIdentity item={item} />
            <StatusBadge status="ready">Ready</StatusBadge>
          </div>
        ))}
        {queue && queue.items.length === 0 && (
          <EmptyState kind="Applications" />
        )}
      </div>
      <QueuePagination
        pagination={queue?.pagination}
        currentCursor={state.analysisCursor}
        disabled={state.analysisRunning}
        onFirst={() => {
          session.setCursors(null, state.resumeCursor)
          session.load()
        }}
        onNext={() => {
          session.setCursors(
            queue?.pagination.nextCursor ?? null,
            state.resumeCursor,
          )
          session.load()
        }}
      />
      <AnalysisResult
        result={state.analysisResult}
        onDismiss={() => session.dismissAnalysisResult()}
      />
      <ErrorCallout errors={queue?.errors} />
      <ErrorCallout
        errors={queue?.validationFailures?.map((failure) => failure.message)}
      />
    </Section>
  )
}

function ResultLinks({ result }: { result: CreateResumeResponse | null }) {
  if (!result) return null
  if (!result.ok)
    return (
      <>
        <ErrorCallout errors={result.errors} />
        <ErrorCallout
          errors={result.validationFailures?.map((failure) => failure.message)}
        />
        {result.cleanup && (
          <div className="cleanup-status">
            <span>Cleanup</span>
            {Object.entries(result.cleanup).map(([key, value]) => (
              <small key={key}>
                {key}: {String(value)}
              </small>
            ))}
          </div>
        )}
      </>
    )
  return (
    <div className="output-links">
      <span>
        {result.result === 'already_created'
          ? 'Existing outputs'
          : 'Created outputs'}
      </span>
      <a href={result.resume?.url} target="_blank" rel="noreferrer">
        Resume <ArrowIcon />
      </a>
      {result.note?.url && (
        <a href={result.note.url} target="_blank" rel="noreferrer">
          Fit analysis <ArrowIcon />
        </a>
      )}
      {result.pdf?.downloadUrl && (
        <a href={result.pdf.downloadUrl} target="_blank" rel="noreferrer">
          PDF <ArrowIcon />
        </a>
      )}
    </div>
  )
}

function ResumeSection({
  state,
  session,
}: {
  state: DashboardState
  session: DashboardSession
}) {
  const queue = state.resumeQueue
  const ready = state.health?.checks?.resumes === 'ready'
  return (
    <Section
      eyebrow="02 · Tailor"
      title="Resume Creation"
      meta={`${queue?.queueCount ?? '—'} waiting`}
      status={ready ? 'ready' : 'blocked'}
    >
      <div className="section-description">
        <p>
          Create one evidence-backed Job-Specific Resume at a time. Outputs
          remain visible after the queue refreshes.
        </p>
      </div>
      <div className="queue-table resume-table">
        <div className="queue-head">
          <span>Eligible Application</span>
          <span>Match</span>
          <span>Action</span>
        </div>
        {queue?.items?.map((item) => {
          const active = state.activeResumeId === item.applicationId
          return (
            <div className="queue-row" key={item.applicationId}>
              <QueueIdentity item={item} />
              <strong className="score">{item.matchScore}%</strong>
              <button
                className="row-button"
                type="button"
                disabled={!ready || Boolean(state.activeResumeId)}
                onClick={() => session.createResume(item.applicationId)}
              >
                {active ? (
                  <>
                    <Spinner /> Creating
                  </>
                ) : (
                  'Create resume'
                )}
              </button>
            </div>
          )
        })}
        {queue && queue.items.length === 0 && <EmptyState kind="Resumes" />}
      </div>
      <QueuePagination
        pagination={queue?.pagination}
        currentCursor={state.resumeCursor}
        disabled={Boolean(state.activeResumeId)}
        onFirst={() => {
          session.setCursors(state.analysisCursor, null)
          session.load()
        }}
        onNext={() => {
          session.setCursors(
            state.analysisCursor,
            queue?.pagination.nextCursor ?? null,
          )
          session.load()
        }}
      />
      {Object.entries(state.resumeResults).map(([applicationId, result]) => (
        <ResultLinks key={applicationId} result={result} />
      ))}
      <ErrorCallout errors={queue?.errors} />
      <ErrorCallout
        errors={queue?.validationFailures?.map((failure) => failure.message)}
      />
    </Section>
  )
}

export function App() {
  const [state, setState] = useState<DashboardState | null>(null)
  const [batchLimit, setBatchLimit] = useState(5)
  const [theme, setTheme] = useState(
    () => localStorage.getItem('merida-theme') || 'light',
  )
  const client = useMemo(() => createDashboardClient(), [])
  const session = useMemo(
    () => createDashboardSession(client, setState),
    [client],
  )
  const view = state || session.getState()

  useEffect(() => {
    session.subscribe(setState)
    session.load()
  }, [session])

  useEffect(() => {
    if (!view.analysisResult) return undefined
    const timer = window.setTimeout(() => session.dismissAnalysisResult(), 8000)
    return () => window.clearTimeout(timer)
  }, [view.analysisResult, session])

  const toggleTheme = () => {
    const next = theme === 'light' ? 'dark' : 'light'
    localStorage.setItem('merida-theme', next)
    setTheme(next)
  }

  return (
    <div className={cx('app-shell', theme === 'dark' && 'theme-dark')}>
      <header className="topbar">
        <Brand />
        <nav aria-label="Primary">
          <span className="is-active">Dashboard</span>
          <a href="https://www.notion.so" target="_blank" rel="noreferrer">
            Open Notion <ArrowIcon />
          </a>
        </nav>
        <div className="topbar-actions">
          <button
            type="button"
            onClick={toggleTheme}
            aria-label="Toggle color theme"
          >
            {theme === 'light' ? '◐' : '◑'}
          </button>
          <button
            type="button"
            onClick={() => session.load()}
            disabled={view.loading}
          >
            {view.loading ? <Spinner /> : 'Refresh'}
          </button>
        </div>
      </header>
      <main>
        <Readiness health={view.health} settings={view.settings} />
        <ErrorCallout errors={view.errors} />
        <AnalysisSection
          state={view}
          session={session}
          batchLimit={batchLimit}
          setBatchLimit={setBatchLimit}
        />
        <ResumeSection state={view} session={session} />
      </main>
      <footer>
        <span>Merida · local-first application workflow</span>
        <span>Records live in Notion · secrets stay in FastAPI</span>
      </footer>
    </div>
  )
}
