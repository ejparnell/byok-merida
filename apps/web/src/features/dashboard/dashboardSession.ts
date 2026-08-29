import type {
  AnalysisRunResponse,
  AnalysisRunSnapshot,
  ResumeArtifactSetSnapshot,
  ResumeRunResponse,
  ResumeRunSnapshot,
} from '@merida/api-client'
import type {
  DashboardApiError,
  DashboardClient,
  DashboardSnapshot,
} from '../../shared/api/dashboardClient.ts'

const clampTarget = (value: unknown) => {
  const numeric = Number(value)
  return Math.max(
    1,
    Math.min(10, Math.trunc(Number.isFinite(numeric) ? numeric : 5)),
  )
}
const operatorError = (error: unknown) => error as DashboardApiError

export const isAnalysisRunActive = (run: AnalysisRunSnapshot | null): boolean =>
  Boolean(run && run.lifecycle !== 'finished')

export type DashboardState = {
  loading: boolean
  health: DashboardSnapshot['health'] | null
  settings: DashboardSnapshot['settings'] | null
  analysisQueue: DashboardSnapshot['analysisQueue'] | null
  resumeQueue: DashboardSnapshot['resumeQueue'] | null
  analysisCursor: string | null
  resumeCursor: string | null
  analysisStarting: boolean
  analysisCancelPending: boolean
  analysisRun: AnalysisRunSnapshot | null
  resumeStarting: boolean
  resumeCancelPending: boolean
  resumeRun: ResumeRunSnapshot | null
  resumeQuarantines: ResumeArtifactSetSnapshot[]
  errors: string[]
}

export type AnalysisPollScheduler = {
  schedule(task: () => Promise<void>, delayMs: number): unknown
  cancel(handle: unknown): void
}

export type DashboardSessionOptions = {
  scheduler?: AnalysisPollScheduler
  pollIntervalMs?: number
  createIdempotencyKey?: () => string
}

export interface DashboardSession {
  getState(): DashboardState
  subscribe(next: (state: DashboardState) => void): void
  setCursors(analysisCursor: string | null, resumeCursor: string | null): void
  load(options?: {
    reset?: boolean
    checkActiveAnalysisRun?: boolean
  }): Promise<DashboardSnapshot | null>
  runAnalysis(target: unknown): Promise<AnalysisRunResponse | null>
  cancelAnalysisRun(): Promise<AnalysisRunResponse | null>
  startResumeRun(target: unknown): Promise<ResumeRunResponse | null>
  cancelResumeRun(): Promise<ResumeRunResponse | null>
  actOnResumeArtifact(
    artifact: ResumeArtifactSetSnapshot,
    kind: 'reconcile' | 'compensate',
  ): Promise<void>
  dispose(): void
}

const defaultScheduler: AnalysisPollScheduler = {
  schedule(task, delayMs) {
    return globalThis.setTimeout(() => void task(), delayMs)
  },
  cancel(handle) {
    globalThis.clearTimeout(handle as ReturnType<typeof setTimeout>)
  },
}

export function createDashboardSession(
  client: DashboardClient,
  onChange: (state: DashboardState) => void = () => {},
  options: DashboardSessionOptions = {},
): DashboardSession {
  const scheduler = options.scheduler || defaultScheduler
  const pollIntervalMs = options.pollIntervalMs ?? 1000
  const createIdempotencyKey =
    options.createIdempotencyKey || (() => globalThis.crypto.randomUUID())
  let pollHandle: unknown = null
  let polling = false
  let disposed = false
  const refreshedTerminalRuns = new Set<string>()
  let state: DashboardState = {
    loading: false,
    health: null,
    settings: null,
    analysisQueue: null,
    resumeQueue: null,
    analysisCursor: null,
    resumeCursor: null,
    analysisStarting: false,
    analysisCancelPending: false,
    analysisRun: null,
    resumeStarting: false,
    resumeCancelPending: false,
    resumeRun: null,
    resumeQuarantines: [],
    errors: [],
  }

  const publish = (patch: Partial<DashboardState>) => {
    state = { ...state, ...patch }
    onChange(state)
  }

  const cancelScheduledPoll = () => {
    if (pollHandle === null) return
    scheduler.cancel(pollHandle)
    pollHandle = null
  }

  const schedulePoll = () => {
    cancelScheduledPoll()
    if (
      disposed ||
      (!isAnalysisRunActive(state.analysisRun) &&
        (!state.resumeRun || state.resumeRun.lifecycle === 'finished'))
    )
      return
    pollHandle = scheduler.schedule(pollDurableResources, pollIntervalMs)
  }

  const acceptResumeRun = (run: ResumeRunSnapshot) => {
    if (
      state.resumeRun?.runId === run.runId &&
      state.resumeRun.revision > run.revision
    )
      return
    publish({ resumeRun: run })
    if (run.lifecycle !== 'finished') schedulePoll()
  }

  const acceptAnalysisRun = async (run: AnalysisRunSnapshot) => {
    const current = state.analysisRun
    if (current?.runId === run.runId) {
      const currentUpdatedAt = Date.parse(current.updatedAt)
      const nextUpdatedAt = Date.parse(run.updatedAt)
      if (
        (current.lifecycle === 'finished' && run.lifecycle !== 'finished') ||
        (Number.isFinite(currentUpdatedAt) &&
          Number.isFinite(nextUpdatedAt) &&
          nextUpdatedAt < currentUpdatedAt)
      ) {
        return
      }
    }
    publish({ analysisRun: run })
    if (isAnalysisRunActive(run)) {
      schedulePoll()
      return
    }

    cancelScheduledPoll()
    if (refreshedTerminalRuns.has(run.runId)) return
    refreshedTerminalRuns.add(run.runId)
    publish({ analysisCursor: null, resumeCursor: null })
    await load({ reset: true, checkActiveAnalysisRun: false })
  }

  async function pollAnalysisRun() {
    pollHandle = null
    const run = state.analysisRun
    if (disposed || polling || !run || run.lifecycle === 'finished') return
    polling = true
    try {
      const result = await client.getAnalysisRun(run.runId)
      if (disposed) return
      await acceptAnalysisRun(result.run)
    } catch (error) {
      const failure = operatorError(error)
      publish({
        errors: [
          failure.message || 'Analysis Run progress could not be refreshed.',
        ],
      })
    } finally {
      polling = false
      if (isAnalysisRunActive(state.analysisRun)) schedulePoll()
    }
  }

  async function pollDurableResources() {
    pollHandle = null
    await Promise.all([
      pollAnalysisRun(),
      (async () => {
        const run = state.resumeRun
        if (!run || run.lifecycle === 'finished') return
        try {
          acceptResumeRun((await client.getResumeRun(run.runId)).run)
        } catch (error) {
          publish({ errors: [operatorError(error).message] })
        }
      })(),
    ])
    schedulePoll()
  }

  async function load({
    reset = false,
    checkActiveAnalysisRun = true,
  }: {
    reset?: boolean
    checkActiveAnalysisRun?: boolean
  } = {}): Promise<DashboardSnapshot | null> {
    const analysisCursor = reset ? null : state.analysisCursor
    const resumeCursor = reset ? null : state.resumeCursor
    publish({ loading: true, errors: [] })
    try {
      const data = await client.loadDashboard({ analysisCursor, resumeCursor })
      publish({
        ...data,
        analysisCursor,
        resumeCursor,
        loading: checkActiveAnalysisRun,
        errors: data.errors || [],
      })
      if (checkActiveAnalysisRun) {
        try {
          const active = await client.getActiveAnalysisRun()
          if (active.run) await acceptAnalysisRun(active.run)
        } catch (error) {
          const failure = operatorError(error)
          publish({
            errors: [
              ...state.errors,
              failure.message || 'Active Analysis Run could not be loaded.',
            ],
          })
        }
        try {
          const [activeResume, quarantines] = await Promise.all([
            client.getActiveResumeRun(),
            client.listResumeArtifactQuarantines(),
          ])
          if (activeResume.run) acceptResumeRun(activeResume.run)
          else {
            const latest = await client.getLatestResumeRun()
            if (latest.run) acceptResumeRun(latest.run)
          }
          publish({ resumeQuarantines: quarantines.items })
        } catch (error) {
          publish({ errors: [...state.errors, operatorError(error).message] })
        }
      }
      publish({ loading: false })
      return data
    } catch (error) {
      const failure = operatorError(error)
      if (
        failure.code === 'invalid_cursor' &&
        (analysisCursor || resumeCursor)
      ) {
        publish({ analysisCursor: null, resumeCursor: null, loading: false })
        return load({ reset: true, checkActiveAnalysisRun })
      }
      publish({
        loading: false,
        errors: [failure.message || 'The local backend could not be reached.'],
      })
      return null
    }
  }

  return {
    getState: () => state,
    subscribe(next: (state: DashboardState) => void) {
      disposed = false
      onChange = next
      next(state)
    },
    setCursors(analysisCursor: string | null, resumeCursor: string | null) {
      publish({ analysisCursor, resumeCursor })
    },
    load,
    async runAnalysis(target: unknown) {
      if (state.analysisStarting || isAnalysisRunActive(state.analysisRun)) {
        return null
      }
      const idempotencyKey = createIdempotencyKey()
      publish({ analysisStarting: true, errors: [] })
      try {
        const result = await client.runAnalysis(
          clampTarget(target),
          idempotencyKey,
        )
        publish({ analysisStarting: false })
        await acceptAnalysisRun(result.run)
        return result
      } catch (error) {
        const failure = operatorError(error)
        if (failure.code === 'analysis_run_active' && failure.activeRunId) {
          try {
            const result = await client.getAnalysisRun(failure.activeRunId)
            publish({ analysisStarting: false, errors: [] })
            await acceptAnalysisRun(result.run)
            return result
          } catch (followError) {
            const followFailure = operatorError(followError)
            publish({
              analysisStarting: false,
              errors: [
                followFailure.message ||
                  'The active Analysis Run could not be loaded.',
              ],
            })
            return null
          }
        }
        publish({
          analysisStarting: false,
          errors: [
            failure.message || 'Application Analysis could not be started.',
          ],
        })
        return null
      }
    },
    async cancelAnalysisRun() {
      const run = state.analysisRun
      if (
        !run ||
        run.lifecycle === 'finished' ||
        state.analysisCancelPending ||
        disposed
      ) {
        return null
      }
      publish({ analysisCancelPending: true, errors: [] })
      try {
        const result = await client.cancelAnalysisRun(run.runId)
        publish({ analysisCancelPending: false })
        await acceptAnalysisRun(result.run)
        return result
      } catch (error) {
        const failure = operatorError(error)
        publish({
          analysisCancelPending: false,
          errors: [
            failure.message || 'The Analysis Run could not be cancelled.',
          ],
        })
        return null
      }
    },
    async startResumeRun(target: unknown) {
      if (
        state.resumeStarting ||
        (state.resumeRun && state.resumeRun.lifecycle !== 'finished')
      )
        return null
      publish({ resumeStarting: true, errors: [] })
      try {
        const result = await client.startResumeRun(
          clampTarget(target),
          createIdempotencyKey(),
        )
        publish({ resumeStarting: false })
        acceptResumeRun(result.run)
        return result
      } catch (error) {
        publish({
          resumeStarting: false,
          errors: [
            operatorError(error).message || 'Resume Run could not be started.',
          ],
        })
        return null
      }
    },
    async cancelResumeRun() {
      const run = state.resumeRun
      if (!run || run.lifecycle === 'finished' || state.resumeCancelPending)
        return null
      publish({ resumeCancelPending: true, errors: [] })
      try {
        const result = await client.cancelResumeRun(run.runId)
        publish({ resumeCancelPending: false })
        acceptResumeRun(result.run)
        return result
      } catch (error) {
        publish({
          resumeCancelPending: false,
          errors: [operatorError(error).message],
        })
        return null
      }
    },
    async actOnResumeArtifact(artifact, kind) {
      try {
        const result = await client.actOnResumeArtifact(
          artifact.artifactSetId,
          kind,
          artifact.revision,
          createIdempotencyKey(),
        )
        publish({
          resumeQuarantines: state.resumeQuarantines.map((item) =>
            item.artifactSetId === result.artifactSet.artifactSetId
              ? result.artifactSet
              : item,
          ),
        })
      } catch (error) {
        publish({ errors: [operatorError(error).message] })
      }
    },
    dispose() {
      disposed = true
      cancelScheduledPoll()
    },
  }
}
