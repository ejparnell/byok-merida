import type {
  CreateResumeResponse,
  RunApplicationAnalysisResponse,
} from '@merida/api-client'
import type {
  DashboardClient,
  DashboardSnapshot,
} from '../../shared/api/dashboardClient.ts'

const clampLimit = (value: unknown) =>
  Math.max(1, Math.min(10, Number(value) || 5))
const operatorError = (error: unknown) => error as Error & { code?: string }

export type DashboardState = {
  loading: boolean
  health: DashboardSnapshot['health'] | null
  settings: DashboardSnapshot['settings'] | null
  analysisQueue: DashboardSnapshot['analysisQueue'] | null
  resumeQueue: DashboardSnapshot['resumeQueue'] | null
  analysisCursor: string | null
  resumeCursor: string | null
  analysisRunning: boolean
  analysisResult: RunApplicationAnalysisResponse | null
  activeResumeId: string | null
  resumeResults: Record<string, CreateResumeResponse>
  errors: string[]
}

export interface DashboardSession {
  getState(): DashboardState
  subscribe(next: (state: DashboardState) => void): void
  setCursors(analysisCursor: string | null, resumeCursor: string | null): void
  load(options?: { reset?: boolean }): Promise<DashboardSnapshot | null>
  runAnalysis(limit: unknown): Promise<RunApplicationAnalysisResponse | null>
  createResume(applicationId: string): Promise<CreateResumeResponse | null>
  dismissAnalysisResult(): void
}

export function createDashboardSession(
  client: DashboardClient,
  onChange: (state: DashboardState) => void = () => {},
): DashboardSession {
  let state: DashboardState = {
    loading: false,
    health: null,
    settings: null,
    analysisQueue: null,
    resumeQueue: null,
    analysisCursor: null,
    resumeCursor: null,
    analysisRunning: false,
    analysisResult: null,
    activeResumeId: null,
    resumeResults: {},
    errors: [],
  }

  const publish = (patch: Partial<DashboardState>) => {
    state = { ...state, ...patch }
    onChange(state)
  }

  const load = async ({ reset = false } = {}) => {
    const analysisCursor = reset ? null : state.analysisCursor
    const resumeCursor = reset ? null : state.resumeCursor
    publish({ loading: true, errors: [] })
    try {
      const data = await client.loadDashboard({ analysisCursor, resumeCursor })
      publish({
        ...data,
        analysisCursor,
        resumeCursor,
        loading: false,
        errors: data.errors || [],
      })
      return data
    } catch (error) {
      const failure = operatorError(error)
      if (
        failure.code === 'invalid_cursor' &&
        (analysisCursor || resumeCursor)
      ) {
        publish({ analysisCursor: null, resumeCursor: null, loading: false })
        return load({ reset: true })
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
      onChange = next
      next(state)
    },
    setCursors(analysisCursor: string | null, resumeCursor: string | null) {
      publish({ analysisCursor, resumeCursor })
    },
    async load(options: { reset?: boolean } = {}) {
      return load(options)
    },
    async runAnalysis(limit: unknown) {
      if (state.analysisRunning) return null
      publish({ analysisRunning: true, analysisResult: null, errors: [] })
      try {
        const result = await client.runAnalysis(clampLimit(limit))
        publish({ analysisRunning: false, analysisResult: result })
        const queueChanged =
          result.ok &&
          result.result === 'completed' &&
          ((result.succeeded || 0) > 0 || (result.repaired || 0) > 0)
        if (queueChanged) {
          publish({ analysisCursor: null, resumeCursor: null })
          await load({ reset: true })
        } else {
          await load()
        }
        return result
      } catch (error) {
        publish({
          analysisRunning: false,
          errors: [
            operatorError(error).message || 'Analysis could not be completed.',
          ],
        })
        return null
      }
    },
    async createResume(applicationId: string) {
      if (state.activeResumeId) return null
      publish({ activeResumeId: applicationId, errors: [] })
      try {
        const result = await client.createResume(applicationId)
        publish({
          activeResumeId: null,
          resumeResults: { ...state.resumeResults, [applicationId]: result },
          resumeCursor:
            result.ok && result.result === 'created'
              ? null
              : state.resumeCursor,
        })
        await load()
        return result
      } catch (error) {
        publish({
          activeResumeId: null,
          errors: [
            operatorError(error).message ||
              'Resume Creation could not be completed.',
          ],
        })
        return null
      }
    },
    dismissAnalysisResult() {
      publish({ analysisResult: null })
    },
  }
}
