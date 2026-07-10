const TRACKING_PARAM_NAMES = new Set([
  "fbclid",
  "gclid",
  "msclkid",
  "mc_cid",
  "mc_eid",
  "igshid",
  "ref",
  "ref_src",
  "source",
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_content",
  "utm_term",
  "utm_id",
]);

export function canonicalizeJobUrl(input) {
  if (!input) {
    return null;
  }

  let parsed;
  try {
    parsed = new URL(input);
  } catch {
    return null;
  }

  parsed.protocol = parsed.protocol.toLowerCase();
  parsed.hostname = parsed.hostname.toLowerCase();

  for (const key of Array.from(parsed.searchParams.keys())) {
    const lowerKey = key.toLowerCase();
    if (lowerKey.startsWith("utm_") || TRACKING_PARAM_NAMES.has(lowerKey)) {
      parsed.searchParams.delete(key);
    }
  }

  if (!shouldKeepFragment(parsed.hash)) {
    parsed.hash = "";
  }

  if (parsed.pathname.length > 1) {
    parsed.pathname = parsed.pathname.replace(/\/+$/g, "");
  }

  return parsed.toString();
}

export function getCapturedUrlPair(input) {
  const jobUrl = canonicalizeJobUrl(input);
  if (!jobUrl) {
    return { jobUrl: null, capturedUrl: input || null };
  }

  const capturedUrl = String(input);
  return {
    jobUrl,
    capturedUrl: capturedUrl === jobUrl ? null : capturedUrl,
  };
}

function shouldKeepFragment(hash) {
  if (!hash) {
    return false;
  }

  return /job|posting|position|req|requisition|jobid|job-id|gh_jid/i.test(hash);
}
