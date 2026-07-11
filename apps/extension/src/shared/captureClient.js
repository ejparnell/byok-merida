import {
  confirmApplication,
  createClient,
  getHealth,
  prepareApplication,
} from '@merida/api-client'

const operatorError = (error) => {
  if (error instanceof Error) return error
  return new Error(error?.error?.message || error?.errors?.[0] || 'The API request failed.')
}

const invoke = async (request) => {
  try {
    return await request
  } catch (error) {
    throw operatorError(error)
  }
}

export function createCaptureClient(settings, options = {}) {
  const generatedClient = createClient({
    baseUrl: settings.backendUrl,
    fetch: options.fetch,
    responseStyle: 'data',
    throwOnError: true,
  })
  const protectedHeaders = () => ({ 'X-Capture-Token': settings.captureToken })

  return {
    health: () => invoke(getHealth({ client: generatedClient })),
    prepare: (evidence) => invoke(prepareApplication({
      client: generatedClient,
      body: { evidence },
      headers: protectedHeaders(),
    })),
    confirm: (draft) => invoke(confirmApplication({
      client: generatedClient,
      body: { draft },
      headers: protectedHeaders(),
    })),
  }
}
