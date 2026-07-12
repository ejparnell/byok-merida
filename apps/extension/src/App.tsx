import { useEffect, useMemo, useState } from 'react'
import { Spinner, StatusDot } from '@merida/ui'
import type {
  ConfirmApplicationResponse,
  PreparedApplicationDraft,
} from '@merida/api-client'

import { createCaptureSession } from './session/captureSession.ts'
import type {
  CapturePhase,
  CaptureSession,
  CaptureState,
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

function Progress({ phase }: { phase: CapturePhase }) {
  const parsing = phase === 'parsing'
  const confirming = phase === 'confirming'
  return (
    <div className="progress" role="status" aria-live="polite">
      <Spinner />
      <span>
        {confirming
          ? 'Saving reviewed Application'
          : parsing
            ? 'Finding review fields'
            : 'Collecting source evidence'}
      </span>
      <h1>
        {confirming
          ? 'Creating in Notion'
          : parsing
            ? 'Parsing Application'
            : 'Reading current page'}
      </h1>
      <p>
        {confirming
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

function Idle({ onFill, errors }: { onFill: () => void; errors?: string[] }) {
  return (
    <div className="idle-view">
      <div className="source-card">
        <span>Current source</span>
        <strong>Active Chrome tab</strong>
        <p>
          Read the job posting, review important fields, then create it in
          Notion.
        </p>
      </div>
      <button className="primary large" type="button" onClick={onFill}>
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
}: {
  state: CaptureState
  session: CaptureSession
  onNewCapture: () => void
}) {
  const review = state.review
  if (!review) return null
  const update = (event: React.ChangeEvent<HTMLInputElement>) =>
    session.updateReview(
      event.target.name as keyof PreparedApplicationDraft,
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
      <div className="content-preview">
        <span>Job Content preview</span>
        <p>
          {review.jobContentPreview ||
            'Readable Job Content is retained in memory for confirmation.'}
        </p>
      </div>
      <ErrorCallout errors={state.errors} />
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

  const collectAndPrepare = async ({ discard = false } = {}) => {
    if (health.phase !== 'ready') return
    try {
      if (!pendingEvidence) session.beginReading()
      const collected = pendingEvidence || (await collectCaptureEvidence())
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
      session.clear()
      setHealth({ phase: 'blocked', errors: [(error as Error).message] })
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
    if (state.phase !== 'reviewing' || !globalThis.chrome?.tabs)
      return undefined
    const checkSource = async () => {
      const [tab] = await chrome.tabs.query({
        active: true,
        currentWindow: true,
      })
      if (tab?.id && tab.url)
        session.sourceChanged({ tabId: tab.id, url: tab.url })
    }
    const onActivated = () => checkSource()
    const onUpdated = (
      _tabId: number,
      changeInfo: chrome.tabs.OnUpdatedInfo,
    ) => {
      if (changeInfo.url) checkSource()
    }
    chrome.tabs.onActivated.addListener(onActivated)
    chrome.tabs.onUpdated.addListener(onUpdated)
    window.addEventListener('focus', checkSource)
    return () => {
      chrome.tabs.onActivated.removeListener(onActivated)
      chrome.tabs.onUpdated.removeListener(onUpdated)
      window.removeEventListener('focus', checkSource)
    }
  }, [state.phase, session])
  useEffect(() => {
    if (state.phase === 'reviewing' && state.missingFields.length) {
      const field = state.missingFields[0]
      document.querySelector<HTMLInputElement>(`[name="${field}"]`)?.focus()
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
        {state.phase === 'idle' && health.phase === 'ready' && (
          <Idle onFill={() => collectAndPrepare()} errors={state.errors} />
        )}
        {state.phase === 'reviewing' && (
          <ReviewForm
            state={state}
            session={session}
            onNewCapture={() => collectAndPrepare()}
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
