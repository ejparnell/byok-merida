import test from "node:test";
import assert from "node:assert/strict";
import { canonicalizeJobUrl, getCapturedUrlPair } from "../lib/url.js";

test("canonicalizeJobUrl removes tracking params and preserves job-identifying params", () => {
  const url = canonicalizeJobUrl("https://Example.com/jobs/view?gh_jid=123&utm_source=mail&foo=bar&gclid=abc#top");

  assert.equal(url, "https://example.com/jobs/view?gh_jid=123&foo=bar");
});

test("canonicalizeJobUrl keeps job-identifying fragments", () => {
  const url = canonicalizeJobUrl("https://example.com/careers#job-123?utm_source=nope");

  assert.equal(url, "https://example.com/careers#job-123?utm_source=nope");
});

test("getCapturedUrlPair keeps original captured URL when canonical differs", () => {
  const pair = getCapturedUrlPair("https://example.com/jobs/123/?utm_campaign=x");

  assert.equal(pair.jobUrl, "https://example.com/jobs/123");
  assert.equal(pair.capturedUrl, "https://example.com/jobs/123/?utm_campaign=x");
});
