# Job Gathering Options

Status: research note, not an architecture decision  
Reviewed: 2026-08-12

## Short conclusion

Merida should treat gathering and capturing as two different stages.

- A gathered item is a **lead**: it can be incomplete, duplicated, or irrelevant.
- A captured `Job Posting` has enough reliable content for Application Analysis and Resume Creation.

The strongest no-paid-job-API approach is a hybrid:

1. Read job-alert emails to discover roles broadly.
2. Enrich leads from first-party ATS feeds or the employer's own career page where possible.
3. Deduplicate and run cheap filters before using AI to rank likely matches.
4. Promote only useful, complete leads into Merida's existing Application Capture workflow.
5. Keep LinkedIn-only leads in a manual-review state instead of automating LinkedIn.

For Merida's current single-user, local-first shape, local Gmail API polling is the best first prototype. If Merida later becomes a multi-user hosted product, filtered email forwarding to a dedicated ingest address is likely the better onboarding model because it avoids requesting access to an entire mailbox.

## Options at a glance

| Option | Coverage | Cost | Effort | Main tradeoff | Suggested role |
| --- | --- | --- | --- | --- | --- |
| Job-alert email ingestion | Broad; reuses LinkedIn, Indeed, Wellfound, Google, and employer alerts | No job API fee | Low–medium | Alerts often contain only a summary, not the full description | **Best discovery source** |
| Public ATS APIs and feeds | High-quality current postings from selected employers | Usually free public GET access | Medium | Mostly company-by-company rather than global search | **Best enrichment and watchlist source** |
| Free public job feeds/APIs | Varies by source and geography | Free or free registration | Low–medium | Narrow coverage, delays, attribution, and usage terms | Useful supplements |
| Employer career-page monitor | Any allowlisted company site | No API fee | Medium–high | Sites change; some require JavaScript rendering | Fallback for target employers |
| AI/browser agent | Potentially broad outside restricted sites | Model/runtime cost | High | Brittle, harder to audit, and vulnerable to hostile page content | Last-resort extractor, not primary collector |
| LinkedIn scraper/browser agent | LinkedIn search results and job pages | Often advertised as free | High | Explicit platform-policy and account risk | **Avoid** |
| Unofficial aggregator or scraping API | Potentially broad | Free tiers may exist | Low initially | Unclear provenance, unstable pricing/access, and downstream terms | Do not make it a core dependency |

## 1. Job-alert email ingestion

This gives Merida broad discovery without having an agent search LinkedIn. LinkedIn officially supports daily or weekly email alerts, with up to 20 active alerts. Indeed, Wellfound, and Google also support email alerts, so one ingestion pipeline can accept several sources.

An alert should initially create a lead containing source, source-message ID, title, company, location, snippet, URL, and received time. It should not automatically become an `Application` unless Merida has a readable full job description.

### Ways to receive the email

- **Local Gmail API polling:** Query only a dedicated label or sender pattern on a schedule. This preserves Merida's local-first architecture and has no additional API charge at normal personal volume. Reading message bodies requires a restricted Gmail scope. Google lists personal-use apps as an exception to restricted-scope verification, but a generally distributed product would need to address OAuth verification and possibly a security assessment.
- **Filtered forwarding to an ingest address:** The user makes a Gmail filter that forwards only job alerts to a unique Merida address. This avoids mailbox-wide OAuth. Cloudflare Email Routing and an Email Worker can receive the messages within its free limits, but this introduces cloud processing and normally requires a domain. Mailgun offers a similar parsed inbound route with a limited free allowance.
- **Gmail push notifications:** Gmail `watch` plus Google Pub/Sub provides faster delivery, but watches must be renewed at least every seven days and notifications still require subsequent Gmail API reads. It is better suited to a later hosted version than the first local prototype.
- **IMAP:** Works across more mail providers and can run locally, but needs broad mailbox credentials/OAuth and reliable long-lived connection handling. It is viable for a personal tool but less attractive as a product integration.
- **Apps Script or self-hosted n8n:** Useful for proving the workflow quickly. They reduce initial coding, but add a second workflow/runtime outside Merida and are less attractive as the permanent product boundary.

Email parsing should be deterministic first, with AI only as a fallback when a template changes. Email HTML, links, and text are untrusted input: do not load trackers, execute links, or let email text issue instructions to an agent.

## 2. Public ATS APIs and feeds

These are the cleanest way to obtain complete descriptions directly from employers. Merida can maintain a watchlist of interesting companies and poll their public boards.

Good first adapters are:

- **Greenhouse:** public Job Board API; `content=true` includes full descriptions.
- **Lever:** public postings API with structured JSON.
- **Ashby:** public job-board API with descriptions, locations, remote status, and optional compensation.
- **SmartRecruiters:** public company posting endpoints with search and pagination.
- **Recruitee:** public careers-site offers endpoint.
- **Personio:** employer-enabled XML job feed.
- **Workable:** a global XML feed exists for jobs published to Jobs by Workable; it is broader but requires streaming and aggressive local filtering.

Most of these APIs are tenant-scoped, so they are excellent for a curated company watchlist but are not a universal job search API. The source job ID and canonical apply URL make deduplication much more reliable than title matching alone.

## 3. Free public feeds and APIs

These can widen coverage without becoming the core of the system:

- **CareerOneStop / National Labor Exchange:** broad US private, state, and public listings; requires free registration and a bearer token.
- **USAJOBS:** structured current US federal openings; requires an API key and has requester/use terms to review before productizing.
- **We Work Remotely:** public RSS feeds that require attribution and links back.
- **Jobicy:** free JSON, RSS, and MCP access for remote roles; delayed listings and fair-use restrictions apply.
- **Remotive:** free remote-jobs API/RSS; results are delayed and require attribution/link-back.
- **Arbeitnow:** no-key feed focused mainly on European and remote jobs.
- **Google Alerts, Indeed alerts, and Wellfound alerts:** useful additional discovery emails that can enter the same ingestion path as LinkedIn alerts.

Every source needs its own small adapter and recorded usage terms. Free access is not the same as unrestricted redistribution.

## 4. Employer career-page monitoring

For known company sites without a supported ATS feed:

1. Read `robots.txt` and site terms.
2. Discover job URLs through XML sitemaps, RSS, or Atom where available.
3. Parse `schema.org/JobPosting` JSON-LD from individual job pages.
4. Use a browser renderer or AI extraction only for allowlisted sites where ordinary HTML extraction fails.

`JobPosting` structured data can provide title, description, organization, dates, location, remote eligibility, employment type, salary, and application information. It standardizes extraction but does not solve discovery, and implementation quality varies by site.

## 5. Where AI agents help

AI is more useful after collection than as the collector:

- normalize inconsistent titles and locations;
- extract fields when a permitted page lacks structured data;
- perform a cheap preliminary fit classification;
- explain why a lead was accepted, rejected, or needs review;
- prioritize which incomplete LinkedIn leads deserve manual capture.

A scheduled connector is cheaper, more reliable, and easier to audit for stable email/API/RSS inputs. A browser agent is reasonable only as an allowlisted fallback for public employer sites.

## LinkedIn boundary

LinkedIn explicitly says it does not allow third-party software or browser extensions that scrape, modify, or automate activity on its website. Its User Agreement also prohibits scripts, robots, crawlers, browser plugins, and other methods used to scrape or copy its services, plus unauthorized automated access. The documented Job Posting API is an approved-partner interface for publishing jobs to LinkedIn, not a public job-search API, and LinkedIn is not currently accepting new Job Posting API partnerships outside its stated route.

Therefore:

- use LinkedIn's own email alerts for discovery;
- do not have a server or browser agent open LinkedIn search results or job pages;
- treat a LinkedIn-only alert as incomplete and require manual review/copying;
- where the user can reach the employer's own ATS/career page, capture or enrich from that first-party source;
- treat use of Merida's current extension directly on LinkedIn pages as policy risk, even when initiated by the user.

Parsing an alert delivered to the user's own inbox is materially lower risk than automated access to LinkedIn, but LinkedIn does not document it as an approved data API. Avoid retaining or republishing full LinkedIn-origin content and obtain legal review before scaling this into a commercial multi-user product.

## Suggested first experiment

Build the smallest end-to-end experiment around existing LinkedIn alert emails:

```text
dedicated Gmail label
  -> local scheduled poll
  -> deterministic alert parser
  -> lead deduplication
  -> ATS/employer enrichment when available
  -> preliminary match filter
  -> review queue
  -> existing Application Capture only when content is complete
```

The experiment should answer three questions before investing in a larger crawler:

1. How many alert entries can be parsed consistently?
2. How often can a lead be enriched into a complete posting without accessing LinkedIn?
3. Does preliminary filtering reduce the review queue enough to be useful?

If Gmail OAuth setup proves too awkward, substitute filtered forwarding plus an inbound Email Worker without changing the rest of the pipeline.

## Primary sources

### LinkedIn and alert sources

- [LinkedIn job alerts](https://www.linkedin.com/help/linkedin/answer/a511279/job-alerts-on-linkedin?lang=en)
- [LinkedIn automated activity policy](https://www.linkedin.com/help/linkedin/answer/a1341543)
- [LinkedIn User Agreement](https://www.linkedin.com/legal/user-agreement)
- [LinkedIn Job Posting API overview](https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/overview?view=li-lts-2026-03)
- [Gmail selective forwarding](https://support.google.com/mail/answer/10957?hl=en)
- [Indeed job alerts](https://support.indeed.com/hc/en-us/articles/204488890-Starting-Stopping-and-Managing-Job-Alerts)
- [Wellfound saved searches and alerts](https://help.wellfound.com/article/782-saved-searches)
- [Google Alerts](https://support.google.com/websearch/answer/4815696?hl=en)

### Email integration

- [Gmail message search](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)
- [Gmail push notifications](https://developers.google.com/workspace/gmail/api/guides/push)
- [Gmail API scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Gmail API usage limits](https://developers.google.com/workspace/gmail/api/reference/quota)
- [Google restricted-scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification)
- [Cloudflare Email Service pricing](https://developers.cloudflare.com/email-service/platform/pricing/)
- [Cloudflare Email Routing](https://developers.cloudflare.com/email-service/get-started/route-emails/)
- [Cloudflare Email Service limits](https://developers.cloudflare.com/email-service/platform/limits/)
- [Mailgun inbound routes](https://documentation.mailgun.com/docs/mailgun/user-manual/receive-forward-store/receive-http)
- [n8n Community edition](https://docs.n8n.io/deploy/host-n8n/community-edition-features)

### Job sources and extraction

- [Greenhouse Job Board API](https://developers.greenhouse.io/job-board.html)
- [Lever Postings API](https://github.com/lever/postings-api)
- [Ashby Job Postings API](https://developers.ashbyhq.com/docs/public-job-posting-api)
- [SmartRecruiters Posting API endpoints](https://developers.smartrecruiters.com/docs/endpoints)
- [Recruitee Careers Site API](https://docs.recruitee.com/reference/intro-to-careers-site-api)
- [Personio XML job integration](https://support.personio.de/hc/en-us/articles/207576365-Integrate-jobs-from-Personio-into-your-company-website-via-XML)
- [Workable XML job feed](https://help.workable.com/hc/en-us/articles/4420464031767-Utilizing-the-XML-Job-Feed)
- [CareerOneStop developer API](https://www.careeronestop.org/Developers/WebAPI/web-api.aspx)
- [USAJOBS Search API](https://developer.usajobs.gov/api-reference/get-api-search)
- [We Work Remotely RSS](https://weworkremotely.com/remote-job-rss-feed)
- [Jobicy feeds and API](https://jobicy.com/jobs-rss-feed)
- [Remotive public API](https://remotive.com/remote-jobs/api)
- [Arbeitnow API](https://www.arbeitnow.com/blog/job-board-api)
- [`schema.org/JobPosting`](https://schema.org/JobPosting)
- [Google JobPosting structured-data guidance](https://developers.google.com/search/docs/appearance/structured-data/job-posting)
- [Google sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)
- [Robots Exclusion Protocol, RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html)
