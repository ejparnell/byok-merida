const DEFAULTS = { backendUrl: 'http://127.0.0.1:8000', captureToken: '' }

export async function getExtensionSettings() {
  if (!globalThis.chrome?.storage?.local) {
    const fallback = JSON.parse(localStorage.getItem('merida-extension-settings') || '{}')
    return { ...DEFAULTS, ...fallback }
  }
  return { ...DEFAULTS, ...(await chrome.storage.local.get(Object.keys(DEFAULTS))) }
}

export async function saveExtensionSettings(settings) {
  const safe = { backendUrl: settings.backendUrl.trim().replace(/\/$/, ''), captureToken: settings.captureToken }
  if (!globalThis.chrome?.storage?.local) {
    localStorage.setItem('merida-extension-settings', JSON.stringify(safe))
    return safe
  }
  await chrome.storage.local.set(safe)
  return safe
}
