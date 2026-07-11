export function createCaptureClient(settings) {
  const request = async (path, options = {}) => {
    const response = await fetch(`${settings.backendUrl}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.protected ? { 'X-Capture-Token': settings.captureToken } : {}),
      },
    })
    const body = await response.json().catch(() => null)
    if (!response.ok) throw new Error(body?.error?.message || body?.errors?.[0] || `Request failed (${response.status}).`)
    return body
  }
  return {
    health: () => request('/api/v1/health'),
    prepare: (evidence) => request('/api/v1/applications/prepare', { method: 'POST', protected: true, body: JSON.stringify({ evidence }) }),
    confirm: (draft) => request('/api/v1/applications/confirm', { method: 'POST', protected: true, body: JSON.stringify({ draft }) }),
  }
}
