import {
  confirmApplication,
  createClient,
  getApplicationCaptureMatches,
  getHealth,
  invokeApiData,
  prepareApplication,
} from '@merida/api-client'
import type {
  ConfirmApplicationRequest,
  ConfirmApplicationResponse,
  CaptureMatchesResponse,
  HealthResponse,
  PrepareApplicationRequest,
  PrepareApplicationResponse,
} from '@merida/api-client'

export type ExtensionSettings = { backendUrl: string; captureToken: string }

export interface CaptureClient {
  health(): Promise<HealthResponse>
  matches(companyName: string, role: string): Promise<CaptureMatchesResponse>
  prepare(
    evidence: PrepareApplicationRequest['evidence'],
  ): Promise<PrepareApplicationResponse>
  confirm(
    draft: ConfirmApplicationRequest['draft'],
  ): Promise<ConfirmApplicationResponse>
}

export function createCaptureClient(
  settings: ExtensionSettings,
  options: { fetch?: typeof fetch } = {},
): CaptureClient {
  const generatedClient = createClient({
    baseUrl: settings.backendUrl,
    fetch: options.fetch,
    throwOnError: true,
  })
  const protectedHeaders = () => ({ 'X-Capture-Token': settings.captureToken })

  return {
    health: () =>
      invokeApiData(
        getHealth<true>({ client: generatedClient, throwOnError: true }),
      ),
    matches: (companyName, role) =>
      invokeApiData(
        getApplicationCaptureMatches<true>({
          client: generatedClient,
          query: { companyName, role },
          headers: protectedHeaders(),
          throwOnError: true,
        }),
      ),
    prepare: (evidence) =>
      invokeApiData(
        prepareApplication<true>({
          client: generatedClient,
          body: { evidence },
          headers: protectedHeaders(),
          throwOnError: true,
        }),
      ),
    confirm: (draft) =>
      invokeApiData(
        confirmApplication<true>({
          client: generatedClient,
          body: { draft },
          headers: protectedHeaders(),
          throwOnError: true,
        }),
      ),
  }
}
