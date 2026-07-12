import {
  confirmApplication,
  createClient,
  getHealth,
  invokeApiData,
  prepareApplication,
} from '@merida/api-client'
import type {
  ConfirmApplicationRequest,
  ConfirmApplicationResponse,
  HealthResponse,
  PrepareApplicationRequest,
  PrepareApplicationResponse,
} from '@merida/api-client'

export type ExtensionSettings = { backendUrl: string; captureToken: string }

export interface CaptureClient {
  health(): Promise<HealthResponse>
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
