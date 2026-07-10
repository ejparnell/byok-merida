import test from "node:test";
import assert from "node:assert/strict";
import {
  buildAnalysisBlocks,
  extractJobContentFromBlocks,
  hasAnalysisSection,
  parseAndValidateAnalysisJson,
} from "../lib/analysisBlocks.js";

test("extractJobContentFromBlocks reads only the Job Content section", () => {
  const content = extractJobContentFromBlocks([
    heading("heading_2", "Capture Summary"),
    bullet("Source: https://example.com"),
    heading("heading_2", "Job Content"),
    paragraph("Build RESTful APIs with FastAPI."),
    bullet("Use PostgreSQL."),
    heading("heading_2", "Job Posting Analysis"),
    paragraph("Old analysis."),
  ]);

  assert.equal(content, "Build RESTful APIs with FastAPI.\nUse PostgreSQL.");
});

test("hasAnalysisSection detects the stable analysis heading", () => {
  assert.equal(hasAnalysisSection([heading("heading_2", "Job Posting Analysis")]), true);
  assert.equal(hasAnalysisSection([heading("heading_2", "Job Content")]), false);
});

test("parseAndValidateAnalysisJson accepts evidenced Skill Signals", () => {
  const jobContent = "Build RESTful APIs with FastAPI and store data in PostgreSQL.";
  const result = parseAndValidateAnalysisJson(JSON.stringify({
    summary: [
      "The role builds backend APIs.",
      "It uses Python API tooling.",
      "It needs database experience.",
    ],
    skillGroups: [
      {
        label: "APIs",
        signals: [{ name: "FastAPI", evidence: "FastAPI" }],
      },
      {
        label: "Databases",
        signals: [{ name: "PostgreSQL", evidence: "PostgreSQL" }],
      },
    ],
  }), jobContent);

  assert.equal(result.summary.length, 3);
  assert.equal(result.skillGroups[0].label, "APIs & Integrations");
  assert.equal(result.skillGroups[1].label, "Databases");
});

test("parseAndValidateAnalysisJson accepts paraphrased evidence when terms are present", () => {
  const jobContent = [
    "We are looking for candidates with experience building production systems.",
    "You should understand database systems, including SQL/NoSQL stores.",
    "Python experience is helpful.",
  ].join(" ");

  const result = parseAndValidateAnalysisJson(JSON.stringify({
    summary: [
      "The role builds production systems.",
      "It expects database knowledge.",
      "It values Python experience.",
    ],
    skillGroups: [
      {
        label: "Databases",
        signals: [
          {
            name: "SQL and NoSQL",
            evidence: "Knowledge of database systems (SQL or NoSQL)",
          },
        ],
      },
    ],
  }), jobContent);

  assert.equal(result.skillGroups[0].label, "Databases");
  assert.equal(result.skillGroups[0].signals[0].name, "SQL and NoSQL");
});

test("parseAndValidateAnalysisJson drops generic Skill Signals without failing concrete signals", () => {
  const jobContent = [
    "Build RESTful and GraphQL APIs with Python and JavaScript.",
    "Use PostgreSQL, DynamoDB, Snowflake, AWS AppSync, and Jest.",
    "Work in cross-functional teams with clear communication.",
  ].join(" ");

  const result = parseAndValidateAnalysisJson(JSON.stringify({
    summary: [
      "The role builds remote education software.",
      "It needs API and database experience.",
      "It includes cross-functional collaboration.",
    ],
    skillGroups: [
      {
        label: "Databases",
        signals: [
          { name: "PostgreSQL", evidence: "PostgreSQL" },
          { name: "DynamoDB", evidence: "DynamoDB" },
        ],
      },
      {
        label: "Workflow & Collaboration",
        signals: [
          { name: "Communication", evidence: "clear communication" },
        ],
      },
      {
        label: "APIs & Integrations",
        signals: [
          { name: "GraphQL", evidence: "GraphQL APIs" },
        ],
      },
    ],
  }), jobContent);

  assert.deepEqual(
    result.skillGroups.flatMap((group) => group.signals.map((signal) => signal.name)),
    ["PostgreSQL", "DynamoDB", "GraphQL"],
  );
  assert.equal(result.skillGroups.some((group) => group.label === "Workflow & Collaboration"), false);
});

test("parseAndValidateAnalysisJson rejects malformed and unsupported output", () => {
  assert.throws(
    () => parseAndValidateAnalysisJson("{", "Use PostgreSQL."),
    /valid JSON/,
  );

  assert.throws(
    () => parseAndValidateAnalysisJson(JSON.stringify({
      summary: ["Only one sentence."],
      skillGroups: [],
    }), "Use PostgreSQL."),
    /exactly three/,
  );

  assert.throws(
    () => parseAndValidateAnalysisJson(JSON.stringify({
      summary: ["One.", "Two.", "Three."],
      skillGroups: [{ label: "Databases", signals: [{ name: "MongoDB", evidence: "MongoDB" }] }],
    }), "Use PostgreSQL."),
    /not found/,
  );
});

test("buildAnalysisBlocks creates the stable Notion section", () => {
  const blocks = buildAnalysisBlocks({
    summary: ["One.", "Two.", "Three."],
    skillGroups: [
      {
        label: "Databases",
        signals: [{ name: "PostgreSQL", evidence: "PostgreSQL" }],
      },
    ],
  });

  const text = JSON.stringify(blocks);
  assert.match(text, /Job Posting Analysis/);
  assert.match(text, /Summary/);
  assert.match(text, /Skill Signals/);
  assert.match(text, /Databases: PostgreSQL/);
});

function paragraph(content) {
  return block("paragraph", content);
}

function bullet(content) {
  return block("bulleted_list_item", content);
}

function heading(type, content) {
  return block(type, content);
}

function block(type, content) {
  return {
    object: "block",
    type,
    [type]: {
      rich_text: [{ type: "text", plain_text: content, text: { content } }],
    },
  };
}
