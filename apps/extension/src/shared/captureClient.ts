import {
  confirmApplication,
  createClient,
  getHealth,
  invokeApi,
  prepareApplication,
} from '@merida/api-client'

export function createCaptureClient(
  settings: { backendUrl: string; captureToken: string },
  options: { fetch?: typeof fetch } = {},
) {
  const generatedClient = createClient({
    baseUrl: settings.backendUrl,
    fetch: options.fetch,
    responseStyle: 'data',
    throwOnError: true,
  })
  const protectedHeaders = () => ({ 'X-Capture-Token': settings.captureToken })

  return {
    health: (): Promise<any> =>
      invokeApi(getHealth({ client: generatedClient })) as Promise<any>,
    prepare: (evidence: any): Promise<any> =>
      invokeApi(
        prepareApplication({
          client: generatedClient,
          body: { evidence },
          headers: protectedHeaders(),
        }),
      ) as Promise<any>,
    confirm: (draft: any): Promise<any> =>
      invokeApi(
        confirmApplication({
          client: generatedClient,
          body: { draft },
          headers: protectedHeaders(),
        }),
      ) as Promise<any>,
  }
}
