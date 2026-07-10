import { blockPlainText } from "../../jobPostings/lib/analysisBlocks.js";
import { richText } from "../../jobPostings/lib/notionBlocks.js";
import { toPlainSingleLine } from "../../jobPostings/lib/text.js";
import {
  bestTemplateRoleForSourceSection,
  RESUME_TEMPLATE_CONTACT,
  RESUME_TEMPLATE_ROLES,
  resumeTemplateContactLine,
  resumeTemplateRoleCompanyLine,
  resumeTemplateRoleHeading,
} from "./resumeTemplate.js";

export const RESUME_FIT_ANALYSIS_HEADING = "Resume Fit Analysis";
export const JOB_SPECIFIC_RESUME_HEADING = "Job-Specific Resume";

export function extractMasterResumeEvidenceItems(blocks) {
  const evidence = [];
  let sourceSection = "Resume";
  let counter = 1;

  for (const block of blocks || []) {
    const text = blockPlainText(block);
    if (!text) {
      continue;
    }

    if (block.type === "heading_1" || block.type === "heading_2" || block.type === "heading_3") {
      sourceSection = text;
      evidence.push(evidenceItem(counter, "heading", sourceSection, text));
      counter += 1;
      continue;
    }

    if (block.type === "bulleted_list_item" || block.type === "numbered_list_item") {
      evidence.push(evidenceItem(counter, "bullet", sourceSection, text));
      counter += 1;
      continue;
    }

    if (block.type === "paragraph" || block.type === "quote" || block.type === "callout") {
      const templateRole = roleDetailTemplateMatch(sourceSection, text);
      if (templateRole) {
        sourceSection = resumeTemplateRoleHeading(templateRole);
      }
      evidence.push(evidenceItem(counter, block.type, sourceSection, text));
      counter += 1;
    }
  }

  return evidence;
}

export function extractMasterResumeWorkExperienceRoles(evidenceItems) {
  const grouped = new Map();

  for (const item of evidenceItems || []) {
    const sourceSection = toPlainSingleLine(item.sourceSection || "", 180);
    if (!sourceSection) {
      continue;
    }

    if (!grouped.has(sourceSection)) {
      grouped.set(sourceSection, {
        heading: sourceSection,
        sourceSection,
        evidenceIds: [],
        bulletEvidenceIds: [],
        order: grouped.size,
      });
    }

    const group = grouped.get(sourceSection);
    group.evidenceIds.push(item.id);

    if (item.type === "bullet") {
      group.bulletEvidenceIds.push(item.id);
    }
  }

  const matchedGroups = [];
  const usedTemplateIds = new Set();
  const templateOrder = new Map(RESUME_TEMPLATE_ROLES.map((role, index) => [role.id, index]));

  for (const group of [...grouped.values()].filter((item) => item.bulletEvidenceIds.length > 0)) {
    const templateRole = bestTemplateRoleForSourceSection(group.sourceSection, usedTemplateIds);
    if (!templateRole) {
      continue;
    }

    usedTemplateIds.add(templateRole.id);
    matchedGroups.push({ group, templateRole });
  }

  return matchedGroups
    .sort((left, right) => templateOrder.get(left.templateRole.id) - templateOrder.get(right.templateRole.id))
    .map(({ group, templateRole }, index) => ({
      id: `role-${index + 1}`,
      templateId: templateRole.id,
      heading: resumeTemplateRoleHeading(templateRole),
      title: templateRole.title,
      organization: templateRole.organization,
      dateRange: templateRole.dateRange,
      sourceSection: group.sourceSection,
      evidenceIds: group.evidenceIds,
      bulletEvidenceIds: group.bulletEvidenceIds,
      order: index,
    }));
}

export function buildResumeFitAnalysisBlocks({ fitAnalysis }) {
  const blocks = [
    heading("heading_2", RESUME_FIT_ANALYSIS_HEADING),
    heading("heading_3", "Summary"),
    paragraph(fitAnalysis.summary || "Resume Fit Analysis completed."),
    bullet(`Fit Score: ${percent(fitAnalysis.score?.overallFitScore)}`),
  ];

  if ((fitAnalysis.score?.categoryScores || []).length > 0) {
    blocks.push(heading("heading_3", "Category Coverage"));
    for (const category of fitAnalysis.score.categoryScores) {
      blocks.push(bullet(`${category.category}: ${percent(category.fitScore)} across ${category.requirementCount} requirement(s)`));
    }
  }

  blocks.push(heading("heading_3", "Requirement Evidence Map"));
  for (const requirement of fitAnalysis.score?.requirements || []) {
    blocks.push(bullet(`${toPlainSingleLine(requirement.text, 180)} — ${requirement.evidenceStrength}`));
    for (const match of (requirement.matches || []).slice(0, 2)) {
      blocks.push(bullet(`Evidence: ${toPlainSingleLine(match.evidenceText, 220)} (${match.sourceSection || "Master Resume"})`));
    }
  }

  blocks.push(heading("heading_3", "Gaps"));
  if ((fitAnalysis.score?.gaps || []).length === 0) {
    blocks.push(bullet("No unsupported required gaps were identified."));
  } else {
    for (const gap of fitAnalysis.score.gaps) {
      blocks.push(bullet(`${toPlainSingleLine(gap.text, 180)} — ${gap.evidenceStrength}`));
    }
  }

  blocks.push(heading("heading_3", "Generation Guardrails"));
  blocks.push(bullet("All Master Resume work experiences were preserved when enough source bullets were available."));
  blocks.push(bullet("Unsupported Job Posting requirements were not turned into new resume claims."));

  return blocks;
}

export function buildJobSpecificResumeBlocks({ generatedResume }) {
  const roleByTemplateId = new Map((generatedResume.roles || [])
    .map((role) => [role.templateId, role])
    .filter(([templateId]) => Boolean(templateId)));
  const blocks = [
    heading("heading_1", RESUME_TEMPLATE_CONTACT.name),
    paragraph(resumeTemplateContactLine()),
    heading("heading_2", "Summary"),
    paragraph(generatedResume.summary || ""),
  ];

  for (const templateRole of RESUME_TEMPLATE_ROLES) {
    const role = roleByTemplateId.get(templateRole.id) || {};
    blocks.push(heading("heading_2", templateRole.title));
    blocks.push(paragraph(resumeTemplateRoleCompanyLine(templateRole), { bold: true }));

    for (const bulletText of role.bullets || []) {
      blocks.push(bullet(bulletText));
    }
  }

  return blocks;
}

export function buildGeneratedResumeBlocks({ fitAnalysis, generatedResume }) {
  return [
    ...buildResumeFitAnalysisBlocks({ fitAnalysis }),
    heading("heading_2", JOB_SPECIFIC_RESUME_HEADING),
    ...buildJobSpecificResumeBlocks({ generatedResume }),
  ];
}

function evidenceItem(index, type, sourceSection, text) {
  return {
    id: `evidence-${index}`,
    type,
    sourceSection,
    text,
  };
}

function percent(value) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function roleDetailTemplateMatch(sourceSection, text) {
  if (!isLikelyRoleDetailLine(text)) {
    return null;
  }
  return bestTemplateRoleForSourceSection(`${sourceSection} ${text}`);
}

function isLikelyRoleDetailLine(text) {
  const value = String(text || "");
  return /\|/.test(value) || /\b(?:19|20)\d{2}\b/.test(value);
}

function heading(type, content) {
  return block(type, content);
}

function paragraph(content, options = {}) {
  return block("paragraph", content, options);
}

function bullet(content) {
  return block("bulleted_list_item", content);
}

function block(type, content, options = {}) {
  return {
    object: "block",
    type,
    [type]: {
      rich_text: richText(content).map((part) => options.bold
        ? { ...part, annotations: { ...(part.annotations || {}), bold: true } }
        : part),
    },
  };
}
