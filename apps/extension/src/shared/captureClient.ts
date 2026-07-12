import {
  confirmApplication,
  createClient,
  getHealth,
  invokeData,
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
    responseStyle: 'data',
    throwOnError: true,
  })
  const protectedHeaders = () => ({ 'X-Capture-Token': settings.captureToken })

  return {
    health: () =>
      invokeData<HealthResponse>(getHealth({ client: generatedClient })),
    prepare: (evidence) =>
      invokeData<PrepareApplicationResponse>(
        prepareApplication({
          client: generatedClient,
          body: { evidence },
          headers: protectedHeaders(),
        }),
      ),
    confirm: (draft) =>
      invokeData<ConfirmApplicationResponse>(
        confirmApplication({
          client: generatedClient,
          body: { draft },
          headers: protectedHeaders(),
        }),
      ),
  }
}
