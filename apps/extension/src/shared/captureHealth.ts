import type { CaptureClient } from './captureClient.ts'

export type ExtensionHealth = {
  phase: 'checking' | 'ready' | 'blocked' | 'offline'
  errors: string[]
}

export async function readCaptureHealth(
  activeClient: CaptureClient,
  captureToken: string,
): Promise<ExtensionHealth> {
  if (!captureToken) {
    return {
      phase: 'blocked',
      errors: ['Add a Capture token in extension settings.'],
    }
  }
  try {
    const result = await activeClient.health()
    const ready =
      result.checks.settings === 'ready' && result.checks.notion === 'ready'
    return {
      phase: ready ? 'ready' : 'blocked',
      errors: ready ? [] : result.errors,
    }
  } catch (error) {
    return { phase: 'offline', errors: [(error as Error).message] }
  }
}
