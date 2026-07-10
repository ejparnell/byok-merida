import test from "node:test";
import assert from "node:assert/strict";
import { ApplicationReadyResumeDraft } from "../lib/applicationReadyResumeDraft.js";
import { extractMasterResumeEvidenceItems } from "../lib/resumeBlocks.js";
import { RESUME_FAILURE_REASONS } from "../types/contracts.js";

test("ApplicationReadyResumeDraft creates fixed-template blocks from Master Resume evidence", async () => {
  const draft = new ApplicationReadyResumeDraft({
    resumeGenerator: fakeResumeGenerator(),
  });

  const result = await draft.create({
    resumeName: "Engineer at Example",
    jobPosting: jobPosting(),
    masterEvidenceItems: templateMasterEvidenceItems(),
    fitScore: fitScoreWithSupportedEvidence([3]),
  });

  assert.equal(hasBlockText(result.fitAnalysisBlocks, "heading_2", "Resume Fit Analysis"), true);
  assert.equal(hasBlockText(result.resumeBlocks, "heading_2", "Resume Fit Analysis"), false);
  assert.equal(hasBlockText(result.resumeBlocks, "heading_1", "Elizabeth Parnell"), true);
  assert.equal(hasBlockText(result.resumeBlocks, "paragraph", "Boston, MA | elizabethprnll@gmail.com | https://www.linkedin.com/in/elizabethjparnell/"), true);
  assert.equal(countResumeBulletsUnderCompanyLine(result.resumeBlocks, "ClinMatchGO | 2025 - Present"), 5);
  assert.equal(countResumeBulletsUnderCompanyLine(result.resumeBlocks, "Break Through Tech | 2025 - Present"), 5);
  assert.equal(countResumeBulletsUnderCompanyLine(result.resumeBlocks, "General Assembly | 2021 - 2024"), 5);
  assert.equal(countResumeBulletsUnderCompanyLine(result.resumeBlocks, "Wayfair | 2018 - 2021"), 5);
});

test("ApplicationReadyResumeDraft recognizes Master Resume sections formatted like the output template", async () => {
  const draft = new ApplicationReadyResumeDraft({
    resumeGenerator: fakeResumeGenerator(),
  });

  const result = await draft.create({
    resumeName: "Engineer at Example",
    jobPosting: jobPosting(),
    masterEvidenceItems: templateFormattedMasterEvidenceItems(),
    fitScore: fitScoreWithSupportedEvidence([4]),
  });

  assert.equal(countResumeBulletsUnderCompanyLine(result.resumeBlocks, "ClinMatchGO | 2025 - Present"), 5);
  assert.equal(countResumeBulletsUnderCompanyLine(result.resumeBlocks, "Break Through Tech | 2025 - Present"), 5);
  assert.equal(countResumeBulletsUnderCompanyLine(result.resumeBlocks, "General Assembly | 2021 - 2024"), 5);
  assert.equal(countResumeBulletsUnderCompanyLine(result.resumeBlocks, "Wayfair | 2018 - 2021"), 5);
});

test("ApplicationReadyResumeDraft repairs claim traces that cite unsupported evidence ids", async () => {
  const draft = new ApplicationReadyResumeDraft({
    resumeGenerator: fakeResumeGenerator({
      generatedResume: {
        name: "Engineer at Example",
        summary: "Engineer focused on REST APIs.",
        skills: ["REST APIs", "PostgreSQL"],
        roles: [
          {
            templateId: "clinmatchgo-software-engineer",
            sourceSection: "Software Engineer, ClinMatchGO",
            heading: "Software Engineer, ClinMatchGO",
            title: "Software Engineer",
            organization: "ClinMatchGO",
            dateRange: "2025 - Present",
            bullets: ["Built REST APIs backed by PostgreSQL."],
            claimTraces: [
              {
                bulletIndex: 0,
                evidenceIds: ["evidence-1"],
                requirementIds: ["req-1"],
              },
            ],
          },
        ],
        sections: [],
      },
    }),
  });

  const result = await draft.create({
    resumeName: "Engineer at Example",
    jobPosting: jobPosting(),
    masterEvidenceItems: templateMasterEvidenceItems(),
    fitScore: fitScoreWithSupportedEvidence([3]),
  });

  assert.equal(countResumeBulletsUnderCompanyLine(result.resumeBlocks, "ClinMatchGO | 2025 - Present"), 5);
});

test("ApplicationReadyResumeDraft fills supported roles to the preferred bullet count", async () => {
  const draft = new ApplicationReadyResumeDraft({
    resumeGenerator: fakeResumeGenerator({
      generatedResume: {
        name: "Engineer at Example",
        summary: "Engineer focused on REST APIs and technical education.",
        skills: ["REST APIs", "PostgreSQL", "React", "MongoDB"],
        roles: [
          {
            templateId: "clinmatchgo-software-engineer",
            sourceSection: "Software Engineer, ClinMatchGO",
            heading: "Software Engineer, ClinMatchGO",
            title: "Software Engineer",
            organization: "ClinMatchGO",
            dateRange: "2025 - Present",
            bullets: ["Built REST API and PostgreSQL workflow 1."],
            claimTraces: [
              {
                bulletIndex: 0,
                evidenceIds: ["evidence-3"],
                requirementIds: ["req-1"],
              },
            ],
          },
          {
            templateId: "general-assembly-lead-instructor",
            sourceSection: "Lead Instructor, General Assembly",
            heading: "Lead Instructor, General Assembly",
            title: "Lead Instructor",
            organization: "General Assembly",
            dateRange: "2021 - 2024",
            bullets: ["Taught JavaScript React and MongoDB architecture 1."],
            claimTraces: [
              {
                bulletIndex: 0,
                evidenceIds: ["evidence-17"],
                requirementIds: ["req-1"],
              },
            ],
          },
        ],
        sections: [],
      },
    }),
  });

  const result = await draft.create({
    resumeName: "Engineer at Example",
    jobPosting: jobPosting(),
    masterEvidenceItems: templateMasterEvidenceItems({ bulletCount: 6 }),
    fitScore: fitScoreWithSupportedEvidence([
      ...range(3, 8),
      ...range(17, 22),
    ]),
  });

  assert.equal(countResumeBulletsUnderCompanyLine(result.resumeBlocks, "ClinMatchGO | 2025 - Present"), 6);
  assert.equal(countResumeBulletsUnderCompanyLine(result.resumeBlocks, "General Assembly | 2021 - 2024"), 6);
});

test("ApplicationReadyResumeDraft preserves every Master Resume role when only one role matches the job", async () => {
  const draft = new ApplicationReadyResumeDraft({
    resumeGenerator: fakeResumeGenerator(),
  });

  const result = await draft.create({
    resumeName: "Engineer at Example",
    jobPosting: jobPosting(),
    masterEvidenceItems: templateMasterEvidenceItems({ bulletCount: 6 }),
    fitScore: fitScoreWithSupportedEvidence(range(3, 8)),
  });

  assert.equal(countResumeBulletsUnderCompanyLine(result.resumeBlocks, "ClinMatchGO | 2025 - Present"), 6);
  assert.equal(countResumeBulletsUnderCompanyLine(result.resumeBlocks, "Break Through Tech | 2025 - Present"), 5);
  assert.equal(countResumeBulletsUnderCompanyLine(result.resumeBlocks, "General Assembly | 2021 - 2024"), 5);
  assert.equal(countResumeBulletsUnderCompanyLine(result.resumeBlocks, "Wayfair | 2018 - 2021"), 5);
});

test("ApplicationReadyResumeDraft keeps bullets in the correct template work experience slot", async () => {
  const draft = new ApplicationReadyResumeDraft({
    resumeGenerator: fakeResumeGenerator({
      generatedResume: {
        name: "Elizabeth Parnell",
        summary: "Engineer focused on REST APIs.",
        skills: [],
        roles: [
          {
            templateId: "wayfair-software-engineer",
            sourceSection: "Software Engineer, Wayfair",
            heading: "Software Engineer, Wayfair",
            title: "Software Engineer",
            organization: "Wayfair",
            dateRange: "2018 - 2021",
            bullets: ["Built REST APIs backed by PostgreSQL."],
            claimTraces: [
              {
                bulletIndex: 0,
                evidenceIds: ["evidence-3"],
                requirementIds: ["req-1"],
              },
            ],
          },
        ],
        sections: [],
      },
    }),
  });

  const result = await draft.create({
    resumeName: "Engineer at Example",
    jobPosting: jobPosting(),
    masterEvidenceItems: templateMasterEvidenceItems(),
    fitScore: fitScoreWithSupportedEvidence([3]),
  });
  const wayfairBullets = resumeBulletsUnderCompanyLine(result.resumeBlocks, "Wayfair | 2018 - 2021");

  assert.equal(wayfairBullets.length, 5);
  assert.equal(wayfairBullets.some((text) => text.includes("Built REST APIs backed by PostgreSQL")), false);
  assert.equal(wayfairBullets.every((text) => text.includes("Supported gift card transaction reliability")), true);
});

test("ApplicationReadyResumeDraft rejects a Master Resume that does not match the fixed template roles", async () => {
  const draft = new ApplicationReadyResumeDraft({
    resumeGenerator: fakeResumeGenerator(),
  });

  await assert.rejects(
    () => draft.create({
      resumeName: "Engineer at Example",
      jobPosting: jobPosting(),
      masterEvidenceItems: extractMasterResumeEvidenceItems([
        block("heading_2", "Work Experience"),
        block("heading_3", "Software Engineer, ClinMatchGO"),
        ...numberedBullets("Built REST APIs backed by PostgreSQL", 5),
      ]),
      fitScore: fitScoreWithSupportedEvidence([3]),
    }),
    (error) => {
      assert.equal(error.reason, RESUME_FAILURE_REASONS.MISSING_MASTER_RESUME);
      assert.match(error.message, /Break Through Tech/);
      assert.match(error.message, /Wayfair/);
      return true;
    },
  );
});

test("ApplicationReadyResumeDraft fails before rendering when a role has fewer than five source bullets", async () => {
  const draft = new ApplicationReadyResumeDraft({
    resumeGenerator: fakeResumeGenerator(),
  });

  await assert.rejects(
    () => draft.create({
      resumeName: "Engineer at Example",
      jobPosting: jobPosting(),
      masterEvidenceItems: templateMasterEvidenceItems({ bulletCount: 4 }),
      fitScore: fitScoreWithSupportedEvidence([3]),
    }),
    (error) => {
      assert.equal(error.reason, RESUME_FAILURE_REASONS.RESUME_GENERATION_FAILED);
      assert.match(error.message, /at least 5/);
      return true;
    },
  );
});

function fakeResumeGenerator(overrides = {}) {
  return {
    async generateResume() {
      return overrides.generatedResume || {
        name: "Elizabeth Parnell",
        summary: "Engineer focused on REST APIs.",
        skills: [],
        roles: [
          {
            templateId: "clinmatchgo-software-engineer",
            sourceSection: "Software Engineer, ClinMatchGO",
            heading: "Software Engineer, ClinMatchGO",
            title: "Software Engineer",
            organization: "ClinMatchGO",
            dateRange: "2025 - Present",
            bullets: ["Built REST APIs backed by PostgreSQL."],
            claimTraces: [
              {
                bulletIndex: 0,
                evidenceIds: ["evidence-3"],
                requirementIds: ["req-1"],
              },
            ],
          },
        ],
        sections: [],
      };
    },
  };
}

function fitScoreWithSupportedEvidence(evidenceIndexes) {
  return {
    ok: true,
    generationAllowed: true,
    overallFitScore: 0.9,
    categoryScores: [{ category: "Full Stack", fitScore: 0.9, requirementCount: 1 }],
    requirements: [
      {
        requirementId: "req-1",
        text: "Build REST APIs with JavaScript React MongoDB and PostgreSQL",
        type: "required skill",
        category: "Full Stack",
        importance: "required",
        evidenceStrength: "direct evidence",
        matches: evidenceIndexes.map((index) => ({
          evidenceId: `evidence-${index}`,
          evidenceStrength: "direct evidence",
          evidenceText: `Master resume evidence ${index}.`,
          sourceSection: "Master Resume",
        })),
      },
    ],
    gaps: [],
  };
}

function jobPosting() {
  return {
    id: "job-page",
    companyName: "Example",
    jobTitle: "Engineer",
    resumeName: "Engineer at Example",
  };
}

function templateMasterEvidenceItems({ bulletCount = 5 } = {}) {
  return extractMasterResumeEvidenceItems(templateMasterChildren({ bulletCount }));
}

function templateMasterChildren({ bulletCount = 5 } = {}) {
  return [
    block("heading_2", "Work Experience"),
    block("heading_3", "Software Engineer, ClinMatchGO"),
    ...numberedBullets("Built REST APIs backed by PostgreSQL", bulletCount),
    block("heading_3", "AI Studio Coach, Break Through Tech"),
    ...numberedBullets("Coached student teams building applied ML apps", bulletCount),
    block("heading_3", "Lead Instructor, General Assembly"),
    ...numberedBullets("Taught JavaScript React and MongoDB architecture", bulletCount),
    block("heading_3", "Software Engineer, Wayfair"),
    ...numberedBullets("Supported gift card transaction reliability", bulletCount),
  ];
}

function templateFormattedMasterEvidenceItems({ bulletCount = 5 } = {}) {
  return extractMasterResumeEvidenceItems([
    block("heading_2", "Work Experience"),
    block("heading_3", "Software Engineer"),
    block("paragraph", "ClinMatchGO | 2025 - Present"),
    ...numberedBullets("Built REST APIs backed by PostgreSQL", bulletCount),
    block("heading_3", "AI Studio Coach"),
    block("paragraph", "Break Through Tech | 2025 - Present"),
    ...numberedBullets("Coached student teams building applied ML apps", bulletCount),
    block("heading_3", "Lead Instructor"),
    block("paragraph", "General Assembly | 2021 - 2024"),
    ...numberedBullets("Taught JavaScript React and MongoDB architecture", bulletCount),
    block("heading_3", "Software Engineer"),
    block("paragraph", "Wayfair | 2018 - 2021"),
    ...numberedBullets("Supported gift card transaction reliability", bulletCount),
  ]);
}

function numberedBullets(prefix, count) {
  return Array.from({ length: count }, (_, index) => block("bulleted_list_item", `${prefix} ${index + 1}.`));
}

function range(start, end) {
  return Array.from({ length: end - start + 1 }, (_, index) => start + index);
}

function countResumeBulletsUnderCompanyLine(blocks, companyLine) {
  return resumeBulletsUnderCompanyLine(blocks, companyLine).length;
}

function resumeBulletsUnderCompanyLine(blocks, companyLine) {
  let waitingForCompanyLine = false;
  let inTargetRole = false;
  const bullets = [];

  for (const blockItem of blocks) {
    const text = blockText(blockItem);

    if (blockItem.type === "heading_2") {
      if (inTargetRole) {
        break;
      }
      waitingForCompanyLine = text !== "Summary";
      continue;
    }

    if (waitingForCompanyLine && blockItem.type === "paragraph") {
      waitingForCompanyLine = false;
      inTargetRole = text === companyLine;
      continue;
    }

    if (inTargetRole && blockItem.type === "bulleted_list_item") {
      bullets.push(text);
    }
  }

  return bullets;
}

function hasBlockText(blocks, type, expectedText) {
  return blocks.some((blockItem) => blockItem.type === type && blockText(blockItem) === expectedText);
}

function blockText(blockItem) {
  const typed = blockItem?.[blockItem.type];
  return (typed?.rich_text || [])
    .map((part) => part.plain_text || part.text?.content || "")
    .join("")
    .trim();
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
