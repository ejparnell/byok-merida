import test from "node:test";
import assert from "node:assert/strict";
import {
  claimSupportedByEvidence,
  evidenceOverlapScore,
  findEvidenceIdsForClaim,
  textSupportsEvidence,
} from "../lib/evidenceSupport.js";

test("textSupportsEvidence accepts exact and alternate evidence phrases", () => {
  const jobContent = "Build RESTful APIs with FastAPI and PostgreSQL.";

  assert.equal(textSupportsEvidence(jobContent, { evidence: "FastAPI" }), true);
  assert.equal(textSupportsEvidence(jobContent, {
    evidence: "Python API framework",
    alternateEvidence: "RESTful APIs",
  }), true);
});

test("textSupportsEvidence accepts meaningful technical tokens without softening unsupported evidence", () => {
  const jobContent = [
    "We are looking for candidates with experience building production systems.",
    "You should understand database systems, including SQL/NoSQL stores.",
  ].join(" ");

  assert.equal(textSupportsEvidence(jobContent, {
    evidence: "Knowledge of database systems (SQL or NoSQL)",
  }), true);
  assert.equal(textSupportsEvidence(jobContent, { evidence: "GraphQL APIs" }), false);
});

test("textSupportsEvidence can preserve Resume Fit Analysis token behavior", () => {
  assert.equal(textSupportsEvidence("Build REST APIs with PostgreSQL.", {
    evidence: "REST API development",
    minTokenRatio: 0.6,
    requireAllTokensWhenShort: false,
    stopwords: new Set(),
    shortTokens: new Set(),
    wholeToken: false,
  }), true);
});

test("claim helpers find and verify claim support", () => {
  const evidenceItems = [
    { id: "evidence-1", text: "Built REST APIs backed by PostgreSQL." },
    { id: "evidence-2", text: "Coached student teams building applied ML apps." },
  ];

  assert.equal(evidenceOverlapScore("Built REST APIs with PostgreSQL.", evidenceItems[0].text) > 0.6, true);
  assert.deepEqual(findEvidenceIdsForClaim("Built REST APIs with PostgreSQL.", evidenceItems), ["evidence-1"]);
  assert.equal(claimSupportedByEvidence("Improved reliability by 12%.", ["Reduced failures by 12%."]), true);
});
