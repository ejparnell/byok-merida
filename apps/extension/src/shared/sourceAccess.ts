export type SourceReference = { tabId: number; url: string }

export type ObservedSource = { tabId: number; url?: string }

export type SourceAccess =
  | { status: 'ready'; source: SourceReference }
  | { status: 'waiting'; source: SourceReference }
  | { status: 'restricted'; source: ObservedSource | null; error: string }

export type PendingCaptureResult =
  | { status: 'ready'; source: SourceReference }
  | { status: 'cancelled' }
  | { status: 'timeout' }

export const RESTRICTED_PAGE_MESSAGE =
  'Chrome does not allow this page to be read. Open a job posting webpage and try again.'

function sourceFromTab(tab: chrome.tabs.Tab): SourceReference | null {
  if (tab.id == null || !tab.url || !/^https?:/.test(tab.url)) return null
  return { tabId: tab.id, url: tab.url }
}

export async function getSourceAccess(): Promise<SourceAccess> {
  if (!globalThis.chrome?.tabs) {
    return {
      status: 'restricted',
      source: null,
      error:
        'Chrome page access is unavailable. Open the installed Merida side panel on a job posting page.',
    }
  }

  let tab: chrome.tabs.Tab | undefined
  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true })
    tab = tabs[0]
  } catch {
    return {
      status: 'restricted',
      source: null,
      error:
        'Chrome page access is unavailable. Open the installed Merida side panel on a job posting page.',
    }
  }
  const source = tab && sourceFromTab(tab)
  if (!source) {
    const observedSource =
      tab && tab.id != null ? { tabId: tab.id, url: tab.url } : null
    return {
      status: 'restricted',
      source: observedSource,
      error: RESTRICTED_PAGE_MESSAGE,
    }
  }

  return {
    status: tab?.status === 'loading' ? 'waiting' : 'ready',
    source,
  }
}

export function observeSourceAccess(
  onChange: (access: SourceAccess) => void,
): () => void {
  if (!globalThis.chrome?.tabs) {
    void getSourceAccess().then(onChange)
    return () => {}
  }

  let active = true
  const refresh = () => {
    void getSourceAccess().then((access) => {
      if (active) onChange(access)
    })
  }
  const onActivated = () => refresh()
  const onUpdated = () => refresh()
  chrome.tabs.onActivated.addListener(onActivated)
  chrome.tabs.onUpdated.addListener(onUpdated)
  refresh()

  return () => {
    active = false
    chrome.tabs.onActivated.removeListener(onActivated)
    chrome.tabs.onUpdated.removeListener(onUpdated)
  }
}

export function waitForSourceReady(
  requestedSource: SourceReference,
  timeoutMs = 15_000,
): Promise<PendingCaptureResult> {
  return new Promise((resolve) => {
    let stop = () => {}
    const finish = (result: PendingCaptureResult) => {
      clearTimeout(timeout)
      stop()
      resolve(result)
    }
    const timeout = setTimeout(() => finish({ status: 'timeout' }), timeoutMs)

    stop = observeSourceAccess((access) => {
      if (
        access.status === 'ready' &&
        access.source.tabId === requestedSource.tabId &&
        access.source.url === requestedSource.url
      ) {
        finish({ status: 'ready', source: access.source })
        return
      }
      if (
        access.status === 'waiting' &&
        access.source.tabId === requestedSource.tabId &&
        access.source.url === requestedSource.url
      ) {
        return
      }
      finish({ status: 'cancelled' })
    })
  })
}
