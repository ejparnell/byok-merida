import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { cx, Spinner, StatusBadge, StatusDot } from '@merida/ui'
import type {
  AnalysisRunSnapshot,
  CreateResumeResponse,
} from '@merida/api-client'

import {
  createDashboardSession,
  isAnalysisRunActive,
} from './features/dashboard/dashboardSession.ts'
import type {
  DashboardSession,
  DashboardState,
} from './features/dashboard/dashboardSession.ts'
import {
  DEFAULT_ANALYSIS_TARGET,
  presentAnalysisRun,
} from './features/dashboard/analysisRunPresentation.ts'
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

function AnalysisRunPanel({
  run,
  cancelPending,
  onCancel,
}: {
  run: AnalysisRunSnapshot | null
  cancelPending: boolean
  onCancel: () => void
}) {
  const presentation = presentAnalysisRun(run, { cancelPending })
  if (!run || !presentation) return null
  return (
    <div
      className={cx('result-panel', `is-${presentation.tone}`)}
      role="status"
    >
      <div className="run-heading">
        <div>
          <span className="eyebrow">Analysis Run</span>
          <strong>{presentation.title}</strong>
          {presentation.reason && <small>{presentation.reason}</small>}
        </div>
        <StatusBadge status={run.lifecycle}>
          {presentation.lifecycleLabel}
        </StatusBadge>
      </div>
      <div className="run-progress" aria-label="Analysis Run progress">
        {presentation.progressRows.map((row) => (
          <div key={row.label}>
            <span>{row.label}</span>
            <strong>{row.value}</strong>
          </div>
        ))}
      </div>
      <p className="run-counts">{presentation.countsSummary}</p>
      <details className="spend-details">
        <summary>Spend details</summary>
        <dl>
          {presentation.spendRows.map((row) => (
            <div key={row.label}>
              <dt>{row.label}</dt>
              <dd>{row.value}</dd>
            </div>
          ))}
        </dl>
      </details>
      {presentation.candidates.length > 0 && (
        <ul className="candidate-results">
          {presentation.candidates.map((candidate) => (
            <li key={candidate.applicationId}>
              <span>{candidate.ordinalLabel}</span>
              <b>{candidate.stateLabel}</b>
              {candidate.reason && <small>{candidate.reason}</small>}
            </li>
          ))}
        </ul>
      )}
      {presentation.showCancel && (
        <div className="run-actions">
          <p>
            Cancelling stops future provider calls. Work already in flight may
            still finish and remain committed.
          </p>
          <button
            className="cancel-button"
            type="button"
            disabled={cancelPending}
            onClick={onCancel}
          >
            {cancelPending ? (
              <>
                <Spinner /> {presentation.cancelLabel}
              </>
            ) : (
              presentation.cancelLabel
            )}
          </button>
        </div>
      )}
    </div>
  )
}

function AnalysisSection({
  state,
  session,
  batchTarget,
  setBatchTarget,
}: {
  state: DashboardState
  session: DashboardSession
  batchTarget: number
  setBatchTarget: (value: number) => void
}) {
  const queue = state.analysisQueue
  const ready = state.health?.checks?.analysis === 'ready'
  const activeRun = isAnalysisRunActive(state.analysisRun)
  const runDisabled =
    !ready || !queue?.queueCount || state.analysisStarting || activeRun
  return (
    <Section
      eyebrow="01 · Enrich"
      title="Application Analysis"
      meta={`${queue?.queueCount ?? '—'} waiting`}
      status={ready ? 'ready' : 'blocked'}
    >
      <div className="section-description">
        <p>
          Choose how many successful Analysis Completions this run should
          pursue. Skipped and failed candidates do not satisfy the target.
        </p>
        <div className="analysis-controls">
          <label>
            <span>Analysis Batch Target</span>
            <input
              type="number"
              min="1"
              max="10"
              step="1"
              value={batchTarget}
              onChange={(event) => setBatchTarget(Number(event.target.value))}
            />
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={runDisabled}
            onClick={() => session.runAnalysis(batchTarget)}
          >
            {state.analysisStarting ? (
              <>
                <Spinner /> Starting run
              </>
            ) : activeRun ? (
              'Run in progress'
            ) : (
              <>
                Run analysis <span aria-hidden="true">→</span>
              </>
            )}
          </button>
        </div>
      </div>
      <div className={cx('queue-table', activeRun && 'is-muted')}>
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
        disabled={activeRun || state.analysisStarting}
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
      <AnalysisRunPanel
        run={state.analysisRun}
        cancelPending={state.analysisCancelPending}
        onCancel={() => void session.cancelAnalysisRun()}
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
  const [batchTarget, setBatchTarget] = useState(DEFAULT_ANALYSIS_TARGET)
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
    void session.load()
    return () => session.dispose()
  }, [session])

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
          batchTarget={batchTarget}
          setBatchTarget={setBatchTarget}
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
