import {
  confirmApplication,
  createClient,
  getHealth,
  invokeApi,
  prepareApplication,
} from '@merida/api-client'

export function createCaptureClient(settings, options = {}) {
  const generatedClient = createClient({
    baseUrl: settings.backendUrl,
    fetch: options.fetch,
    responseStyle: 'data',
    throwOnError: true,
  })
  const protectedHeaders = () => ({ 'X-Capture-Token': settings.captureToken })

  return {
    health: () => invokeApi(getHealth({ client: generatedClient })),
    prepare: (evidence) => invokeApi(prepareApplication({
      client: generatedClient,
      body: { evidence },
      headers: protectedHeaders(),
    })),
    confirm: (draft) => invokeApi(confirmApplication({
      client: generatedClient,
      body: { draft },
      headers: protectedHeaders(),
    })),
  }
}
