import {
  createClient,
  createResume,
  getApplicationAnalysisQueue,
  getHealth,
  getOperatorSettings,
  getResumeCreationQueue,
  invokeApiData,
  runApplicationAnalysis,
} from '@merida/api-client'
import type {
  CreateResumeResponse,
  GetApplicationAnalysisQueueResponse,
  GetResumeCreationQueueResponse,
  HealthResponse,
  OperatorSettingsResponse,
  RunApplicationAnalysisResponse,
} from '@merida/api-client'

export type DashboardSnapshot = {
  health: HealthResponse | null
  settings: OperatorSettingsResponse | null
  analysisQueue: GetApplicationAnalysisQueueResponse | null
  resumeQueue: GetResumeCreationQueueResponse | null
  errors: string[]
}

export interface DashboardClient {
  loadDashboard(cursors: {
    analysisCursor?: string | null
    resumeCursor?: string | null
  }): Promise<DashboardSnapshot>
  runAnalysis(limit: number): Promise<RunApplicationAnalysisResponse>
  createResume(applicationId: string): Promise<CreateResumeResponse>
}

const queueQuery = (cursor?: string | null) => ({
  limit: 5,
  ...(cursor ? { cursor } : {}),
})

export function createDashboardClient(
  options: { baseUrl?: string; fetch?: typeof fetch } = {},
): DashboardClient {
  const generatedClient = createClient({
    baseUrl:
      options.baseUrl || globalThis.location?.origin || 'http://127.0.0.1:8000',
    fetch: options.fetch,
    throwOnError: true,
  })

  return {
    async loadDashboard({
      analysisCursor,
      resumeCursor,
    }: {
      analysisCursor?: string | null
      resumeCursor?: string | null
    }) {
      const results = await Promise.allSettled([
        invokeApiData(
          getHealth<true>({ client: generatedClient, throwOnError: true }),
        ),
        invokeApiData(
          getOperatorSettings<true>({
            client: generatedClient,
            throwOnError: true,
          }),
        ),
        invokeApiData(
          getApplicationAnalysisQueue<true>({
            client: generatedClient,
            query: queueQuery(analysisCursor),
            throwOnError: true,
          }),
        ),
        invokeApiData(
          getResumeCreationQueue<true>({
            client: generatedClient,
            query: queueQuery(resumeCursor),
            throwOnError: true,
          }),
        ),
      ])
      const rejected = results.filter(
        (result): result is PromiseRejectedResult =>
          result.status === 'rejected',
      )
      const invalidCursor = rejected.find(
        (result) =>
          (result.reason as { code?: string })?.code === 'invalid_cursor',
      )
      if (invalidCursor) throw invalidCursor.reason
      const value = <T>(index: number): T | null => {
        const result = results[index]
        return result?.status === 'fulfilled'
          ? (result as PromiseFulfilledResult<T>).value
          : null
      }
      return {
        health: value<HealthResponse>(0),
        settings: value<OperatorSettingsResponse>(1),
        analysisQueue: value<GetApplicationAnalysisQueueResponse>(2),
        resumeQueue: value<GetResumeCreationQueueResponse>(3),
        errors: rejected.map(
          (result) =>
            (result.reason as Error)?.message ||
            'A dashboard section could not be loaded.',
        ),
      }
    },
    runAnalysis(limit: number) {
      return invokeApiData(
        runApplicationAnalysis<true>({
          client: generatedClient,
          body: { limit },
          throwOnError: true,
        }),
      )
    },
    createResume(applicationId: string) {
      return invokeApiData(
        createResume<true>({
          client: generatedClient,
          body: { applicationId },
          throwOnError: true,
        }),
      )
    },
  }
}
