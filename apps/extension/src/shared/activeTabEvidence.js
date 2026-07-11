function collectFromPage() {
  const selectedText = (window.getSelection()?.toString().trim() || '').slice(0, 120000)
  const visibleText = document.body?.innerText?.replace(/\n{3,}/g, '\n\n').trim() || ''
  return {
    url: window.location.href,
    title: document.title,
    selectedText,
    visibleText: visibleText.slice(0, 120000),
    semanticHtml: document.querySelector('main, article, [role="main"]')?.innerHTML?.slice(0, 120000) || '',
  }
}

export async function collectCaptureEvidence() {
  if (!globalThis.chrome?.tabs || !globalThis.chrome?.scripting) {
    return {
      evidence: {
        url: 'https://jobs.example.test/demo/frontend-engineer',
        title: 'Senior Frontend Engineer at Northstar Labs',
        selectedText: '',
        visibleText: 'Northstar Labs is hiring a Senior Frontend Engineer to build accessible React interfaces, REST APIs, design systems, and reliable automated tests.',
        semanticHtml: '',
      },
      source: { tabId: 0, url: 'https://jobs.example.test/demo/frontend-engineer' },
    }
  }
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  if (!tab?.id || !tab.url || /^(chrome|edge|about|chrome-extension):/.test(tab.url)) {
    throw new Error('Chrome does not allow this page to be read. Open a job posting webpage and try again.')
  }
  const results = await chrome.scripting.executeScript({ target: { tabId: tab.id, allFrames: true }, func: collectFromPage })
  const frames = results.map((result) => result.result).filter(Boolean)
  const main = results.find((result) => result.frameId === 0)?.result || frames[0]
  if (!main) throw new Error('No readable page content was found.')
  const selectedText = (frames.map((frame) => frame.selectedText).find(Boolean) || '').slice(0, 120000)
  let remaining = 240000 - selectedText.length
  const visibleText = frames
    .map((frame) => frame.visibleText)
    .filter(Boolean)
    .join('\n\n')
    .slice(0, Math.min(120000, remaining))
  remaining -= visibleText.length
  const semanticHtml = frames
    .map((frame) => frame.semanticHtml)
    .filter(Boolean)
    .join('\n')
    .slice(0, Math.min(120000, remaining))
  const evidence = {
    ...main,
    selectedText,
    visibleText,
    semanticHtml,
  }
  return { evidence, source: { tabId: tab.id, url: tab.url } }
}
