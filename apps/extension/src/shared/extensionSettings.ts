import type { ExtensionSettings } from './captureClient.ts'

const DEFAULTS = { backendUrl: 'http://127.0.0.1:8000', captureToken: '' }

export async function getExtensionSettings(): Promise<ExtensionSettings> {
  if (!globalThis.chrome?.storage?.local) {
    const fallback = JSON.parse(
      localStorage.getItem('merida-extension-settings') || '{}',
    )
    return { ...DEFAULTS, ...fallback }
  }
  const keys = Object.keys(DEFAULTS) as Array<keyof ExtensionSettings>
  return {
    ...DEFAULTS,
    ...(await chrome.storage.local.get(keys)),
  }
}

export async function saveExtensionSettings(
  settings: ExtensionSettings,
): Promise<ExtensionSettings> {
  const safe = {
    backendUrl: settings.backendUrl.trim().replace(/\/$/, ''),
    captureToken: settings.captureToken,
  }
  if (!globalThis.chrome?.storage?.local) {
    localStorage.setItem('merida-extension-settings', JSON.stringify(safe))
    return safe
  }
  await chrome.storage.local.set(safe)
  return safe
}
