import type { PrepareApplicationRequest } from '@merida/api-client'
import { RESTRICTED_PAGE_MESSAGE } from './sourceAccess.ts'
import type { SourceReference } from './sourceAccess.ts'

function collectFromPage() {
  const metadata: Record<string, string> = {}
  document.querySelectorAll('meta[name], meta[property]').forEach((element) => {
    const meta = element as HTMLMetaElement
    const key = meta.getAttribute('property') || meta.getAttribute('name') || ''
    if (key && meta.content) metadata[key.toLowerCase()] = meta.content
  })
  const jsonLd: unknown[] = []
  document
    .querySelectorAll('script[type="application/ld+json"]')
    .forEach((script) => {
      try {
        jsonLd.push(JSON.parse(script.textContent || ''))
      } catch {
        // Ignore malformed page-owned metadata.
      }
    })
  const flatten = (value: unknown): Record<string, unknown>[] => {
    if (Array.isArray(value)) return value.flatMap(flatten)
    if (!value || typeof value !== 'object') return []
    const item = value as Record<string, unknown>
    return [item, ...flatten(item['@graph'])]
  }
  const posting = jsonLd.flatMap(flatten).find((item) => {
    const types = Array.isArray(item['@type']) ? item['@type'] : [item['@type']]
    return types.some(
      (type) => String(type || '').toLowerCase() === 'jobposting',
    )
  })
  const organization = posting?.hiringOrganization as
    Record<string, unknown> | undefined
  const locations = Array.isArray(posting?.jobLocation)
    ? posting?.jobLocation
    : [posting?.jobLocation].filter(Boolean)
  const structuredLocation =
    posting?.jobLocationType === 'TELECOMMUTE'
      ? 'Remote'
      : locations
          .map((location) => {
            const value = location as Record<string, unknown>
            const address = (value.address || value) as Record<string, unknown>
            return [
              address.addressLocality,
              address.addressRegion,
              address.addressCountry,
            ]
              .filter(Boolean)
              .join(', ')
          })
          .filter(Boolean)
          .join('; ')
  const shadowText: string[] = []
  document.querySelectorAll('*').forEach((element) => {
    const root = element.shadowRoot
    const text = root?.textContent?.replace(/\s+/g, ' ').trim()
    if (text) shadowText.push(text)
  })
  const selectedText = (window.getSelection()?.toString().trim() || '').slice(
    0,
    120000,
  )
  const visibleText = [
    document.body?.innerText?.replace(/\n{3,}/g, '\n\n').trim() || '',
    ...shadowText,
  ]
    .filter(Boolean)
    .join('\n\n')
  const metadataText = [
    posting?.description,
    posting?.responsibilities,
    posting?.qualifications,
    posting?.skills,
    metadata['description'],
    metadata['og:description'],
  ]
    .filter(Boolean)
    .join('\n\n')
  return {
    url: window.location.href,
    title: document.title,
    selectedText,
    visibleText: visibleText.slice(0, 120000),
    semanticHtml:
      document
        .querySelector('main, article, [role="main"]')
        ?.innerHTML?.slice(0, 120000) || '',
    metadataText: metadataText.slice(0, 120000),
    structuredJobTitle: String(posting?.title || metadata['og:title'] || ''),
    structuredCompanyName: String(
      organization?.name || metadata['og:site_name'] || '',
    ),
    structuredLocation,
  }
}

export async function collectCaptureEvidence(
  source: SourceReference,
): Promise<CollectedCaptureEvidence> {
  if (!globalThis.chrome?.scripting) {
    throw new Error(
      'Chrome page access is unavailable. Open the installed Merida side panel on a job posting page.',
    )
  }
  let results: Array<{
    frameId?: number
    result?: ReturnType<typeof collectFromPage>
  }>
  try {
    results = await chrome.scripting.executeScript({
      target: { tabId: source.tabId, allFrames: true },
      func: collectFromPage,
    })
  } catch {
    throw new Error(RESTRICTED_PAGE_MESSAGE)
  }
  const frames = results
    .map((result) => result.result)
    .filter((frame): frame is NonNullable<typeof frame> => Boolean(frame))
  const main =
    results.find((result) => result.frameId === 0)?.result || frames[0]
  if (!main) throw new Error('No readable page content was found.')
  const selectedText = (
    frames.map((frame) => frame.selectedText).find(Boolean) || ''
  ).slice(0, 120000)
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
  remaining -= semanticHtml.length
  const metadataText = frames
    .map((frame) => frame.metadataText || '')
    .filter(Boolean)
    .join('\n\n')
    .slice(0, Math.min(120000, Math.max(0, remaining)))
  const evidence = {
    ...main,
    selectedText,
    visibleText,
    semanticHtml,
    metadataText,
  }
  return { evidence, source }
}

export type CollectedCaptureEvidence = {
  evidence: PrepareApplicationRequest['evidence']
  source: SourceReference
}
