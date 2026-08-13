import {
  cancelApplicationAnalysisRun,
  createClient,
  createResume,
  getActiveApplicationAnalysisRun,
  getApplicationAnalysisQueue,
  getApplicationAnalysisRun,
  getHealth,
  getOperatorSettings,
  getResumeCreationQueue,
  invokeApiData,
  runApplicationAnalysis,
} from '@merida/api-client'
import type {
  ActiveAnalysisRunResponse,
  AnalysisRunResponse,
  ApiErrorDetail,
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
  runAnalysis(
    target: number,
    idempotencyKey: string,
  ): Promise<RunApplicationAnalysisResponse>
  getActiveAnalysisRun(): Promise<ActiveAnalysisRunResponse>
  getAnalysisRun(runId: string): Promise<AnalysisRunResponse>
  cancelAnalysisRun(runId: string): Promise<AnalysisRunResponse>
  createResume(applicationId: string): Promise<CreateResumeResponse>
}

export type DashboardApiError = Error & {
  code?: ApiErrorDetail['code']
  requestId?: string | null
  activeRunId?: string | null
  validationFailures?: unknown[]
}

const toDashboardApiError = (error: unknown): DashboardApiError => {
  if (error instanceof Error) return error as DashboardApiError
  const payload = error as {
    error?: ApiErrorDetail
    errors?: string[]
    validationFailures?: unknown[]
  }
  const failure = new Error(
    payload?.error?.message ||
      payload?.errors?.[0] ||
      'The API request failed.',
  ) as DashboardApiError
  failure.code = payload?.error?.code
  failure.requestId = payload?.error?.requestId
  failure.activeRunId = payload?.error?.activeRunId
  failure.validationFailures = payload?.validationFailures
  return failure
}

const invokeDashboardData = async <T extends { data: unknown }>(
  request: Promise<T>,
): Promise<T['data']> => {
  try {
    return (await request).data
  } catch (error) {
    throw toDashboardApiError(error)
  }
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
    async runAnalysis(target: number, idempotencyKey: string) {
      const requestMetadata = {
        target,
        idempotencyKeyPresent: idempotencyKey.length > 0,
        idempotencyKeyLength: idempotencyKey.length,
      }
      console.info('[DEBUG-ANALYSIS-START] sending request', requestMetadata)
      try {
        return await invokeDashboardData(
          runApplicationAnalysis<true>({
            client: generatedClient,
            body: { target },
            headers: { 'Idempotency-Key': idempotencyKey },
            throwOnError: true,
          }),
        )
      } catch (error) {
        const failure = toDashboardApiError(error)
        console.error('[DEBUG-ANALYSIS-START] request rejected', {
          ...requestMetadata,
          code: failure.code,
          message: failure.message,
          validationFailures: failure.validationFailures,
        })
        throw failure
      }
    },
    getActiveAnalysisRun() {
      return invokeDashboardData(
        getActiveApplicationAnalysisRun<true>({
          client: generatedClient,
          throwOnError: true,
        }),
      )
    },
    getAnalysisRun(runId: string) {
      return invokeDashboardData(
        getApplicationAnalysisRun<true>({
          client: generatedClient,
          path: { runId },
          throwOnError: true,
        }),
      )
    },
    cancelAnalysisRun(runId: string) {
      return invokeDashboardData(
        cancelApplicationAnalysisRun<true>({
          client: generatedClient,
          path: { runId },
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
