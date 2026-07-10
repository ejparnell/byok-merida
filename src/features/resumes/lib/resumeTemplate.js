import { normalizeText } from "../../jobPostings/lib/text.js";

export const RESUME_TEMPLATE_CONTACT = Object.freeze({
  name: "Elizabeth Parnell",
  location: "Boston, MA",
  email: "elizabethprnll@gmail.com",
  linkedin: "https://www.linkedin.com/in/elizabethjparnell/",
});

export const RESUME_TEMPLATE_ROLES = Object.freeze([
  {
    id: "clinmatchgo-software-engineer",
    title: "Software Engineer",
    organization: "ClinMatchGO",
    dateRange: "2025 - Present",
    aliases: ["Software Engineer, ClinMatchGO", "ClinMatchGO"],
  },
  {
    id: "break-through-tech-ai-studio-coach",
    title: "AI Studio Coach",
    organization: "Break Through Tech",
    dateRange: "2025 - Present",
    aliases: ["AI Studio Coach, Break Through Tech", "Break Through Tech"],
  },
  {
    id: "general-assembly-lead-instructor",
    title: "Lead Instructor",
    organization: "General Assembly",
    dateRange: "2021 - 2024",
    aliases: ["Lead Instructor, General Assembly", "General Assembly"],
  },
  {
    id: "wayfair-software-engineer",
    title: "Software Engineer",
    organization: "Wayfair",
    dateRange: "2018 - 2021",
    aliases: ["Software Engineer, Wayfair", "Wayfair"],
  },
]);

export function resumeTemplateMarkdown() {
  const lines = [
    `# ${RESUME_TEMPLATE_CONTACT.name}`,
    "",
    resumeTemplateContactLine(),
    "",
    "## Summary",
    "",
    "[Custom summary filled in based on the job description]",
  ];

  for (const role of RESUME_TEMPLATE_ROLES) {
    lines.push(
      "",
      `## ${role.title}`,
      "",
      `**${resumeTemplateRoleCompanyLine(role)}**`,
      "",
      "[5 to 7 bullet points made from the master resume]",
    );
  }

  return lines.join("\n");
}

export function resumeTemplateContactLine() {
  return [
    RESUME_TEMPLATE_CONTACT.location,
    RESUME_TEMPLATE_CONTACT.email,
    RESUME_TEMPLATE_CONTACT.linkedin,
  ].join(" | ");
}

export function resumeTemplateRoleCompanyLine(role) {
  return `${role.organization} | ${role.dateRange}`;
}

export function resumeTemplateRoleHeading(role) {
  return `${role.title}, ${role.organization}`;
}

export function missingResumeTemplateRoles(workExperienceRoles) {
  const matchedIds = new Set((workExperienceRoles || [])
    .map((role) => role.templateId)
    .filter(Boolean));

  return RESUME_TEMPLATE_ROLES.filter((role) => !matchedIds.has(role.id));
}

export function bestTemplateRoleForSourceSection(sourceSection, usedTemplateIds = new Set()) {
  const ranked = RESUME_TEMPLATE_ROLES
    .filter((role) => !usedTemplateIds.has(role.id))
    .map((role) => ({
      role,
      score: scoreSourceSectionForTemplateRole(sourceSection, role),
    }))
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score);

  return ranked[0]?.role || null;
}

function scoreSourceSectionForTemplateRole(sourceSection, role) {
  const normalized = normalizeRoleText(sourceSection);
  const compact = compactRoleText(sourceSection);
  const organization = normalizeRoleText(role.organization);
  const compactOrganization = compactRoleText(role.organization);
  const title = normalizeRoleText(role.title);
  let score = 0;

  if (compactOrganization && compact.includes(compactOrganization)) {
    score += 100;
  }
  if (title && normalized.includes(title)) {
    score += 25;
  }

  for (const alias of role.aliases || []) {
    const normalizedAlias = normalizeRoleText(alias);
    const compactAlias = compactRoleText(alias);
    if (compactAlias && compact.includes(compactAlias)) {
      score += 15;
    } else if (normalizedAlias && normalized.includes(normalizedAlias)) {
      score += 10;
    }
  }

  return score;
}

function compactRoleText(value) {
  return normalizeRoleText(value).replace(/\s+/g, "");
}

function normalizeRoleText(value) {
  return normalizeText(value)
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^\p{L}\p{N}+#.]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}
