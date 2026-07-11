async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(body?.error?.message || body?.errors?.[0] || `Request failed (${response.status}).`)
  }
  return body
}

const queueUrl = (path, cursor) => {
  const params = new URLSearchParams({ limit: '5' })
  if (cursor) params.set('cursor', cursor)
  return `${path}?${params}`
}

export function createDashboardClient() {
  return {
    async loadDashboard({ analysisCursor, resumeCursor }) {
      const [health, settings, analysisQueue, resumeQueue] = await Promise.all([
        request('/api/v1/health'),
        request('/api/v1/operator/settings'),
        request(queueUrl('/api/v1/applications/analysis/queue', analysisCursor)),
        request(queueUrl('/api/v1/resumes/queue', resumeCursor)),
      ])
      return { health, settings, analysisQueue, resumeQueue }
    },
    runAnalysis(limit) {
      return request('/api/v1/applications/analysis/run', {
        method: 'POST',
        body: JSON.stringify({ limit }),
      })
    },
    createResume(applicationId) {
      return request('/api/v1/resumes/create', {
        method: 'POST',
        body: JSON.stringify({ applicationId }),
      })
    },
    resetDemo() {
      return request('/api/v1/demo/reset', { method: 'POST', body: '{}' })
    },
  }
}
