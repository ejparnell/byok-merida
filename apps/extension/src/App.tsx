import { useEffect, useMemo, useState } from 'react'
import { Spinner, StatusDot } from '@merida/ui'
import type { ConfirmApplicationResponse } from '@merida/api-client'

import { createCaptureSession } from './session/captureSession.ts'
import type {
  CapturePhase,
  CaptureSession,
  CaptureState,
  ReviewDraft,
} from './session/captureSession.ts'
import { collectCaptureEvidence } from './shared/activeTabEvidence.ts'
import type { CollectedCaptureEvidence } from './shared/activeTabEvidence.ts'
import { createCaptureClient } from './shared/captureClient.ts'
import type { ExtensionSettings } from './shared/captureClient.ts'
import {
  readCaptureHealth,
  type ExtensionHealth,
} from './shared/captureHealth.ts'
import {
  getExtensionSettings,
  saveExtensionSettings,
} from './shared/extensionSettings.ts'
import {
  getSourceAccess,
  observeSourceAccess,
  waitForSourceReady,
} from './shared/sourceAccess.ts'
import type { SourceAccess } from './shared/sourceAccess.ts'

function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">M</span>
      <strong>Merida</strong>
      <i>Application Capture</i>
    </div>
  )
}

function SettingsSheet({
  settings,
  onSave,
  onClose,
}: {
  settings: ExtensionSettings
  onSave: (settings: ExtensionSettings) => void
  onClose: () => void
}) {
  const [draft, setDraft] = useState(settings)
  return (
    <div className="sheet-backdrop">
      <section
        className="settings-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
      >
        <header>
          <div>
            <span>Extension settings</span>
            <h2 id="settings-title">Local connection</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close settings">
            ×
          </button>
        </header>
        <label>
          <span>Backend URL</span>
          <input
            value={draft.backendUrl}
            onChange={(event) =>
              setDraft({ ...draft, backendUrl: event.target.value })
            }
          />
        </label>
        <label>
          <span>Capture token</span>
          <input
            type="password"
            value={draft.captureToken}
            placeholder="Required"
            onChange={(event) =>
              setDraft({ ...draft, captureToken: event.target.value })
            }
          />
        </label>
        <button className="primary" type="button" onClick={() => onSave(draft)}>
          Save settings
        </button>
        <button
          className="text-button"
          type="button"
          onClick={() =>
            setDraft({ ...draft, backendUrl: 'http://127.0.0.1:8000' })
          }
        >
          Reset backend URL
        </button>
        <p>
          Only the local backend URL and masked Capture token are stored. Job
          Content stays in the active review session.
        </p>
      </section>
    </div>
  )
}

function Progress({ phase }: { phase: CapturePhase | 'waiting' }) {
  const waiting = phase === 'waiting'
  const parsing = phase === 'parsing'
  const confirming = phase === 'confirming'
  return (
    <div className="progress" role="status" aria-live="polite">
      <Spinner />
      <span>
        {waiting
          ? 'Waiting for current page'
          : confirming
            ? 'Saving reviewed Application'
            : parsing
              ? 'Finding review fields'
              : 'Collecting source evidence'}
      </span>
      <h1>
        {waiting
          ? 'Waiting for page'
          : confirming
            ? 'Creating in Notion'
            : parsing
              ? 'Parsing Application'
              : 'Reading current page'}
      </h1>
      <p>
        {waiting
          ? 'Merida will stop waiting after 15 seconds so you can retry.'
          : confirming
            ? 'Your edits remain available if the request fails.'
            : 'Merida keeps full page content only in this side-panel session.'}
      </p>
    </div>
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

function Idle({
  onFill,
  errors,
  sourceAccess,
}: {
  onFill: () => void
  errors?: string[]
  sourceAccess: SourceAccess | null
}) {
  const restricted = sourceAccess?.status === 'restricted'
  const waiting = sourceAccess?.status === 'waiting'
  return (
    <div className="idle-view">
      <div className="source-card">
        <span>Current source</span>
        <strong>
          {restricted
            ? 'Source page unavailable'
            : waiting
              ? 'Source page loading'
              : sourceAccess
                ? 'Active Chrome tab'
                : 'Checking active tab'}
        </strong>
        <p>
          Read the job posting, review important fields, then create it in
          Notion.
        </p>
      </div>
      <button
        className="primary large"
        type="button"
        onClick={onFill}
        disabled={!sourceAccess || restricted}
      >
        Fill form <span aria-hidden="true">→</span>
      </button>
      <ErrorCallout errors={errors} />
      <div className="privacy-note">
        <span>Private by design</span>
        <p>
          No Notion or model credentials live in this extension. Job Content is
          never written to extension storage.
        </p>
      </div>
    </div>
  )
}

function ReviewForm({
  state,
  session,
  onNewCapture,
  sourceErrors,
}: {
  state: CaptureState
  session: CaptureSession
  onNewCapture: () => void
  sourceErrors?: string[]
}) {
  const review = state.review
  if (!review) return null
  const update = (
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) =>
    session.updateReview(
      event.target.name as keyof ReviewDraft,
      event.target.value,
    )
  return (
    <form
      className="review-form"
      onSubmit={(event) => {
        event.preventDefault()
        session.confirm()
      }}
    >
      {state.sourceChanged && (
        <div className="source-warning">
          <strong>Review belongs to a previous tab</strong>
          <p>Your reviewed values have not been replaced.</p>
        </div>
      )}
      <div className="review-heading">
        <span>Review before writing</span>
        <h1>
          {review.role || 'Role'} at {review.companyName || 'Company'}
        </h1>
        <p>
          Application title updates automatically from Role and Company Name.
        </p>
      </div>
      <label>
        <span>
          Company Name <em>Required</em>
        </span>
        <input
          name="companyName"
          value={review.companyName || ''}
          onChange={update}
        />
      </label>
      <label>
        <span>
          Role <em>Required</em>
        </span>
        <input name="role" value={review.role || ''} onChange={update} />
      </label>
      <label>
        <span>Location</span>
        <input
          name="location"
          value={review.location || ''}
          onChange={update}
        />
      </label>
      <label>
        <span>
          Job URL <em>Required</em>
        </span>
        <input name="jobUrl" value={review.jobUrl || ''} onChange={update} />
      </label>
      <label className="content-editor">
        <span>
          Job Content <em>Required</em>
        </span>
        <textarea
          name="jobContent"
          value={review.jobContent}
          onChange={update}
          rows={12}
          aria-describedby="job-content-help"
        />
        <small id="job-content-help">
          Edit the content that will be saved to Notion. It stays in this review
          session until you confirm.
        </small>
      </label>
      <ErrorCallout errors={[...state.errors, ...(sourceErrors || [])]} />
      <button className="primary large" type="submit">
        Create in Notion <span aria-hidden="true">→</span>
      </button>
      <button className="secondary" type="button" onClick={onNewCapture}>
        Read a different page
      </button>
    </form>
  )
}

type CompletedCapture = Exclude<
  ConfirmApplicationResponse,
  { result: 'blocked' }
>

function Complete({
  result,
  onReset,
}: {
  result: CompletedCapture
  onReset: () => void
}) {
  const application = result.application
  return (
    <div className="complete-view" role="status">
      <span className="success-mark">✓</span>
      <i>Capture complete</i>
      <h1>
        {result.result === 'already_captured'
          ? 'Application already captured'
          : 'Application created'}
      </h1>
      <p>
        {application.title} is ready in{' '}
        {result.result === 'already_captured'
          ? 'the existing workspace record'
          : 'Notion'}
        .
      </p>
      <dl>
        <div>
          <dt>Company</dt>
          <dd>{application.companyName}</dd>
        </div>
        <div>
          <dt>Role</dt>
          <dd>{application.role}</dd>
        </div>
      </dl>
      <a
        className="primary large"
        href={application.url}
        target="_blank"
        rel="noreferrer"
      >
        Open in Notion <span aria-hidden="true">↗</span>
      </a>
      <button className="secondary" type="button" onClick={onReset}>
        Capture another Application
      </button>
    </div>
  )
}

function DiscardDialog({
  onCancel,
  onDiscard,
}: {
  onCancel: () => void
  onDiscard: () => void
}) {
  return (
    <div className="dialog-backdrop">
      <section role="dialog" aria-modal="true" aria-labelledby="discard-title">
        <span>Unsaved review</span>
        <h2 id="discard-title">Read a new page?</h2>
        <p>Your edited fields belong to the current Source Page.</p>
        <button className="primary" type="button" onClick={onDiscard}>
          Discard and continue
        </button>
        <button className="secondary" type="button" onClick={onCancel}>
          Keep reviewing
        </button>
      </section>
    </div>
  )
}

export function App() {
  const [settings, setSettings] = useState<ExtensionSettings>({
    backendUrl: 'http://127.0.0.1:8000',
    captureToken: '',
  })
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [health, setHealth] = useState<ExtensionHealth>({
    phase: 'checking',
    errors: [],
  })
  const [sessionState, setSessionState] = useState<CaptureState | null>(null)
  const [pendingEvidence, setPendingEvidence] =
    useState<CollectedCaptureEvidence | null>(null)
  const [discardOpen, setDiscardOpen] = useState(false)
  const [sourceAccess, setSourceAccess] = useState<SourceAccess | null>(null)
  const [sourceErrors, setSourceErrors] = useState<string[]>([])
  const [pendingCapture, setPendingCapture] = useState(false)
  const client = useMemo(() => createCaptureClient(settings), [settings])
  const [session] = useState<CaptureSession>(() =>
    createCaptureSession(client, setSessionState),
  )

  useEffect(() => {
    session.setClient(client)
  }, [client, session])

  const refresh = async (
    activeClient = client,
    captureToken = settings.captureToken,
  ) => {
    setHealth({ phase: 'checking', errors: [] })
    setHealth(await readCaptureHealth(activeClient, captureToken))
  }

  useEffect(() => {
    getExtensionSettings().then(async (loaded) => {
      setSettings(loaded)
      const loadedClient = createCaptureClient(loaded)
      setHealth(await readCaptureHealth(loadedClient, loaded.captureToken))
    })
  }, [])

  useEffect(() => {
    const stop = observeSourceAccess((next) => {
      setSourceAccess(next)
      if (next.status !== 'restricted') setSourceErrors([])
    })
    const refreshSourceAccess = () => {
      void getSourceAccess().then(setSourceAccess)
    }
    window.addEventListener('focus', refreshSourceAccess)
    return () => {
      stop()
      window.removeEventListener('focus', refreshSourceAccess)
    }
  }, [])

  const collectAndPrepare = async ({ discard = false } = {}) => {
    if (health.phase !== 'ready') return

    let collected = pendingEvidence
    if (!collected) {
      setSourceErrors([])
      const access = await getSourceAccess()
      setSourceAccess(access)
      if (access.status === 'restricted') {
        setSourceErrors([access.error])
        return
      }

      let source = access.source
      if (access.status === 'waiting') {
        setPendingCapture(true)
        const outcome = await waitForSourceReady(source)
        setPendingCapture(false)
        if (outcome.status === 'timeout') {
          setSourceErrors(['Page is still loading. Try Fill Form again.'])
          return
        }
        if (outcome.status === 'cancelled') return
        source = outcome.source
      }

      try {
        session.beginReading()
        collected = await collectCaptureEvidence(source)
        const currentAccess = await getSourceAccess()
        setSourceAccess(currentAccess)
        if (
          currentAccess.status !== 'ready' ||
          currentAccess.source.tabId !== source.tabId ||
          currentAccess.source.url !== source.url
        ) {
          session.cancelReading()
          return
        }
      } catch (error) {
        session.cancelReading()
        setSourceErrors([(error as Error).message])
        return
      }
    }

    try {
      const outcome = await session.prepare(
        collected.evidence,
        collected.source,
        { discard },
      )
      if (outcome === 'discard_confirmation_required') {
        setPendingEvidence(collected)
        setDiscardOpen(true)
      } else {
        setPendingEvidence(null)
      }
    } catch (error) {
      session.cancelReading()
      setSourceErrors([(error as Error).message])
    }
  }

  const saveSettings = async (next: ExtensionSettings) => {
    const saved = await saveExtensionSettings(next)
    setSettings(saved)
    setSettingsOpen(false)
    const nextClient = createCaptureClient(saved)
    setHealth(await readCaptureHealth(nextClient, saved.captureToken))
  }

  const state = sessionState || session.getState()
  useEffect(() => {
    if (state.phase === 'reviewing' && sourceAccess?.source)
      session.sourceChanged(sourceAccess.source)
  }, [state.phase, session, sourceAccess])
  useEffect(() => {
    if (state.phase === 'reviewing' && state.missingFields.length) {
      const field = state.missingFields[0]
      document
        .querySelector<HTMLInputElement | HTMLTextAreaElement>(
          `[name="${field}"]`,
        )
        ?.focus()
    }
  }, [state.phase, state.missingFields])
  const readyLabel =
    health.phase === 'ready'
      ? 'Ready to capture'
      : health.phase === 'checking'
        ? 'Checking backend'
        : health.phase === 'offline'
          ? 'Backend offline'
          : 'Capture blocked'
  return (
    <main className="panel-shell">
      <header className="panel-header">
        <Brand />
        <div>
          <button
            type="button"
            onClick={() => refresh()}
            aria-label="Refresh readiness"
          >
            ↻
          </button>
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            aria-label="Open settings"
          >
            ⚙
          </button>
        </div>
      </header>
      <div className="readiness">
        <StatusDot
          status={
            health.phase === 'ready'
              ? 'ready'
              : health.phase === 'checking'
                ? 'checking'
                : 'blocked'
          }
        />
        <span>
          <strong>{readyLabel}</strong>
          <small>{settings.backendUrl}</small>
        </span>
      </div>
      <div className="panel-content" aria-live="polite">
        {health.phase !== 'ready' && state.phase === 'idle' && (
          <>
            <ErrorCallout errors={health.errors} />
            <button
              className="secondary wide"
              type="button"
              onClick={() => setSettingsOpen(true)}
            >
              Open settings
            </button>
          </>
        )}
        {['reading', 'parsing', 'confirming'].includes(state.phase) && (
          <Progress phase={state.phase} />
        )}
        {pendingCapture && <Progress phase="waiting" />}
        {state.phase === 'idle' &&
          health.phase === 'ready' &&
          !pendingCapture && (
            <Idle
              onFill={() => collectAndPrepare()}
              errors={[
                ...state.errors,
                ...(sourceAccess?.status === 'restricted'
                  ? [sourceAccess.error]
                  : []),
                ...sourceErrors,
              ]}
              sourceAccess={sourceAccess}
            />
          )}
        {state.phase === 'reviewing' && !pendingCapture && (
          <ReviewForm
            state={state}
            session={session}
            onNewCapture={() => collectAndPrepare()}
            sourceErrors={[
              ...(sourceAccess?.status === 'restricted'
                ? [sourceAccess.error]
                : []),
              ...sourceErrors,
            ]}
          />
        )}
        {state.phase === 'complete' &&
          state.result &&
          state.result.result !== 'blocked' && (
            <Complete result={state.result} onReset={() => session.clear()} />
          )}
      </div>
      {settingsOpen && (
        <SettingsSheet
          settings={settings}
          onSave={saveSettings}
          onClose={() => setSettingsOpen(false)}
        />
      )}
      {discardOpen && (
        <DiscardDialog
          onCancel={() => {
            setDiscardOpen(false)
            setPendingEvidence(null)
          }}
          onDiscard={() => {
            setDiscardOpen(false)
            collectAndPrepare({ discard: true })
          }}
        />
      )}
    </main>
  )
}
