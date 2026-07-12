from dataclasses import dataclass
import logging
import re
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from ...matching import (
    MATCHING_V1,
    SCORING_POLICY_VERSION,
    EvidenceItem,
    EvidenceMatchingEngine,
    EvidenceMatch,
)
from ..applications.workspace import ApplicationRecord
from .ports import (
    FitRequirement as _RequirementPayload,
    FitRequirementModel,
    FitRequirementsProposal,
    GeneratedBullet as _GeneratedBullet,
    GeneratedResume as _GeneratedResume,
    GeneratedResumeProposal,
    GeneratedRole as _GeneratedRole,
    PromptCategoryCoverage as _PromptCategoryCoverage,
    PromptEvidenceItem as _PromptEvidenceItem,
    PromptRequirement as _PromptRequirement,
    PromptRoleTarget as _PromptRoleTarget,
    ResumeDraftInput,
    ResumeDraftModel,
)
from .workspace import (
    DocumentBlock,
    ResumeArtifactBundle,
    ResumeDocument,
)


logger = logging.getLogger(__name__)


class ResumeEvidenceError(ValueError):
    """The source material cannot support a truthful generated Resume."""


class ResumeModelOutputError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ResumeGenerationError(RuntimeError):
    """A safe feature-owned model or workflow failure."""


@dataclass(frozen=True)
class RequirementFit:
    requirement: _RequirementPayload
    strongest: EvidenceMatch
    matches: tuple[EvidenceMatch, ...]


@dataclass(frozen=True)
class CategoryCoverage:
    category: str
    score: int
    requirement_count: int


@dataclass(frozen=True)
class ResumeFitScore:
    score: int
    requirements: tuple[RequirementFit, ...]
    category_coverage: tuple[CategoryCoverage, ...]
    gaps: tuple[RequirementFit, ...]
    generation_allowed: bool
    scoring_policy: str


@dataclass(frozen=True)
class _RoleSource:
    heading_index: int
    end_index: int
    source_section: str
    evidence_ids: tuple[str, ...]


class _ResumeGraphState(TypedDict, total=False):
    workflow: str
    run_id: str
    application_id: str
    application: ApplicationRecord
    master_resume: ResumeDocument
    evidence: tuple[EvidenceItem, ...]
    roles: tuple[_RoleSource, ...]
    requirements: tuple[_RequirementPayload, ...]
    fit_score: ResumeFitScore
    selected_evidence: tuple[EvidenceItem, ...]
    generation_input: ResumeDraftInput
    generation_attempt: int
    generation_error: str
    generated_payload: GeneratedResumeProposal | None
    generated: _GeneratedResume
    resume: tuple[DocumentBlock, ...]
    note: tuple[DocumentBlock, ...]
    outcome: ResumeArtifactBundle


_NON_WORK_SECTION_NAMES = {
    "summary",
    "skills",
    "education",
    "certifications",
    "certificates",
    "projects",
    "volunteer work",
    "volunteering",
    "publications",
    "awards",
    "languages",
}


class ResumeDocumentGraph:
    def __init__(
        self,
        requirement_model: FitRequirementModel,
        draft_model: ResumeDraftModel,
        matcher: EvidenceMatchingEngine | None = None,
    ):
        self._requirement_model = requirement_model
        self._draft_model = draft_model
        self._matcher = matcher or EvidenceMatchingEngine()
        self._graph = self._build_graph()

    async def build(
        self,
        application: ApplicationRecord,
        master_resume: ResumeDocument,
        *,
        run_id: str | None = None,
        workflow: str = "resume_creation",
    ) -> ResumeArtifactBundle:
        if not application.job_content or application.analysis is None:
            raise ResumeEvidenceError(
                "Readable Job Content and Application Analysis are required."
            )
        try:
            state = await self._graph.ainvoke(
                {
                    "workflow": workflow,
                    "run_id": run_id or f"resume-document:{application.id}",
                    "application_id": application.id,
                    "application": application,
                    "master_resume": master_resume,
                    "generation_attempt": 0,
                }
            )
            return state["outcome"]
        except (ResumeEvidenceError, ResumeModelOutputError):
            raise
        except Exception as error:
            raise ResumeGenerationError(
                "Resume generation could not be completed."
            ) from error

    def _build_graph(self):
        graph = StateGraph(_ResumeGraphState)
        graph.add_node("parse_master_resume_document", self._parse_master_resume)
        graph.add_node("extract_fit_requirements", self._extract_requirements)
        graph.add_node("calculate_fit_score", self._calculate_fit_score)
        graph.add_node("evaluate_generation_gate", self._evaluate_gate)
        graph.add_node("select_prompt_evidence", self._select_prompt_evidence)
        graph.add_node("prepare_resume_generation", self._prepare_generation)
        graph.add_node("generate_resume_draft", self._generate_draft)
        graph.add_node("validate_generated_resume", self._validate_draft)
        graph.add_node("complete_roles_from_source_evidence", self._complete_roles)
        graph.add_node("build_canonical_resume_document", self._build_document)
        graph.add_node("render_resume_fit_analysis_note", self._render_note)
        graph.add_node("complete_resume_document", self._complete)
        graph.add_edge(START, "parse_master_resume_document")
        graph.add_edge("parse_master_resume_document", "extract_fit_requirements")
        graph.add_edge("extract_fit_requirements", "calculate_fit_score")
        graph.add_edge("calculate_fit_score", "evaluate_generation_gate")
        graph.add_edge("evaluate_generation_gate", "select_prompt_evidence")
        graph.add_edge("select_prompt_evidence", "prepare_resume_generation")
        graph.add_edge("prepare_resume_generation", "generate_resume_draft")
        graph.add_edge("generate_resume_draft", "validate_generated_resume")
        graph.add_conditional_edges(
            "validate_generated_resume",
            self._after_draft_validation,
            {
                "repair": "generate_resume_draft",
                "complete": "complete_roles_from_source_evidence",
            },
        )
        graph.add_edge("complete_roles_from_source_evidence", "build_canonical_resume_document")
        graph.add_edge("build_canonical_resume_document", "render_resume_fit_analysis_note")
        graph.add_edge("render_resume_fit_analysis_note", "complete_resume_document")
        graph.add_edge("complete_resume_document", END)
        return graph.compile()

    async def _parse_master_resume(self, state: _ResumeGraphState) -> dict:
        evidence = _evidence_items(state["master_resume"])
        return {
            "evidence": evidence,
            "roles": validate_master_resume_structure(
                state["master_resume"], evidence
            ),
        }

    async def _extract_requirements(self, state: _ResumeGraphState) -> dict:
        return {"requirements": await self._requirements(state["application"])}

    async def _calculate_fit_score(self, state: _ResumeGraphState) -> dict:
        fit_score = _calculate_resume_fit_score(
            state["requirements"], state["evidence"], self._matcher
        )
        logger.info(
            "Resume Fit calculated workflow=%s run_id=%s application_id=%s policy_version=%s requirement_count=%s score=%s generation_allowed=%s",
            state["workflow"],
            state["run_id"],
            state["application_id"],
            fit_score.scoring_policy,
            len(fit_score.requirements),
            fit_score.score,
            fit_score.generation_allowed,
        )
        return {"fit_score": fit_score}

    async def _evaluate_gate(self, state: _ResumeGraphState) -> dict:
        _require_generation_evidence(state["fit_score"])
        return {}

    async def _select_prompt_evidence(self, state: _ResumeGraphState) -> dict:
        return {
            "selected_evidence": _select_prompt_evidence(
                state["evidence"], state["roles"], state["fit_score"]
            )
        }

    async def _prepare_generation(self, state: _ResumeGraphState) -> dict:
        return {
            "generation_input": _resume_input(
                state["application"],
                state["selected_evidence"],
                state["roles"],
                state["fit_score"],
            )
        }

    async def _generate_draft(self, state: _ResumeGraphState) -> dict:
        repair_code = state.get("generation_error") or None
        try:
            payload = await self._draft_model.generate(
                state["generation_input"], repair_code=repair_code
            )
        except ValueError as error:
            payload = None
            repair_code = getattr(error, "code", "invalid_json")
        return {
            "generated_payload": payload,
            "generation_attempt": state.get("generation_attempt", 0) + 1,
            "generation_error": repair_code or "",
        }

    async def _validate_draft(self, state: _ResumeGraphState) -> dict:
        payload = state.get("generated_payload")
        if payload is None:
            return {"generation_error": state.get("generation_error") or "invalid_resume_schema"}
        try:
            generated = payload.resume
            _validate_generated_resume(
                generated,
                state["evidence"],
                state["roles"],
                state["fit_score"],
                self._matcher,
            )
            return {"generated": generated, "generation_error": ""}
        except ResumeModelOutputError as error:
            return {
                "generated": generated,
                "generation_error": error.code,
            }

    def _after_draft_validation(self, state: _ResumeGraphState) -> str:
        if not state.get("generation_error"):
            return "complete"
        return "repair" if state["generation_attempt"] < 2 else "complete"

    async def _complete_roles(self, state: _ResumeGraphState) -> dict:
        generated = state.get("generated")
        if state.get("generation_error"):
            if generated is None:
                raise ResumeModelOutputError(
                    state["generation_error"],
                    "Generated Resume returned invalid JSON.",
                )
            generated = _deterministically_complete_resume(
                generated,
                state["master_resume"],
                state["evidence"],
                state["roles"],
                state["fit_score"],
                self._matcher,
            )
            _validate_generated_resume(
                generated,
                state["evidence"],
                state["roles"],
                state["fit_score"],
                self._matcher,
            )
        assert generated is not None
        if not _claim_supported(
            generated.summary, state["evidence"], self._matcher
        ):
            generated = generated.model_copy(
                update={
                    "summary": _master_summary(state["master_resume"])
                    or state["evidence"][0].text
                }
            )
        return {"generated": generated}

    async def _build_document(self, state: _ResumeGraphState) -> dict:
        return {
            "resume": _render_resume_document(
                state["master_resume"], state["generated"], state["roles"]
            )
        }

    async def _render_note(self, state: _ResumeGraphState) -> dict:
        return {
            "note": _render_fit_note(
                state["application"], state["fit_score"], state["generated"]
            )
        }

    async def _complete(self, state: _ResumeGraphState) -> dict:
        return {
            "outcome": ResumeArtifactBundle(
                resume=state["resume"], note=state["note"]
            )
        }

    async def _requirements(
        self, application: ApplicationRecord
    ) -> tuple[_RequirementPayload, ...]:
        def validate(payload: FitRequirementsProposal) -> tuple[_RequirementPayload, ...]:
            requirements = tuple(payload.requirements)
            seen: set[str] = set()
            for requirement in requirements:
                if requirement.id in seen:
                    raise ResumeModelOutputError(
                        "duplicate_requirement_id",
                        "Fit Requirement IDs must be unique.",
                    )
                seen.add(requirement.id)
                if not _source_contains(application.job_content or "", requirement.evidence):
                    raise ResumeModelOutputError(
                        "unsupported_requirement_evidence",
                        "Fit Requirement evidence was not found in Job Content.",
                    )
            return tuple(
                _normalize_requirement_importance(
                    requirement, application.job_content or ""
                )
                for requirement in requirements
            )

        repair_code = None
        for attempt in range(2):
            try:
                return validate(
                    await self._requirement_model.extract(
                        application.job_content or "",
                        application.analysis,
                        repair_code=repair_code,
                    )
                )
            except (ResumeModelOutputError, ValueError) as error:
                repair_code = getattr(error, "code", "invalid_json")
                if attempt == 1:
                    raise ResumeModelOutputError(
                        repair_code, "Resume generation output could not be validated."
                    ) from error
        raise AssertionError("unreachable")


class DeepSeekResumeDocumentBuilder:
    def __init__(
        self,
        requirement_model: FitRequirementModel,
        draft_model: ResumeDraftModel,
        matcher: EvidenceMatchingEngine | None = None,
    ):
        self._graph = ResumeDocumentGraph(
            requirement_model, draft_model, matcher
        )

    async def build(
        self,
        application: ApplicationRecord,
        master_resume: ResumeDocument,
        *,
        run_id: str | None = None,
        workflow: str = "resume_creation",
    ) -> ResumeArtifactBundle:
        return await self._graph.build(
            application, master_resume, run_id=run_id, workflow=workflow
        )


def validate_master_resume_structure(
    master_resume: ResumeDocument,
    evidence: tuple[EvidenceItem, ...] | None = None,
) -> tuple[_RoleSource, ...]:
    available_evidence = evidence or _evidence_items(master_resume)
    roles = _role_sources(master_resume, available_evidence)
    if not available_evidence or not roles:
        raise ResumeEvidenceError(
            "Master Resume must contain readable work-experience evidence with chronology."
        )
    if any(len(role.evidence_ids) < 5 for role in roles):
        raise ResumeEvidenceError(
            "Every Master Resume work-experience role requires at least five bullet evidence items."
        )
    return roles


def validate_master_resume_readiness(master_resume: ResumeDocument) -> None:
    evidence = _evidence_items(master_resume)
    roles = _role_sources(master_resume, evidence)
    if not evidence or not roles or not any(role.evidence_ids for role in roles):
        raise ResumeEvidenceError(
            "Master Resume must contain a recognizable work-experience section and readable bullet evidence."
        )


def _evidence_items(master_resume: ResumeDocument) -> tuple[EvidenceItem, ...]:
    section = master_resume.record.name
    items = []
    for index, block in enumerate(master_resume.blocks, start=1):
        if block.kind in {"heading_1", "heading_2", "heading_3"}:
            section = block.text
        items.append(
            EvidenceItem(
                id=f"{master_resume.record.id}:block-{index}",
                text=block.text,
                source_section=section,
            )
        )
    return tuple(items)


def _role_sources(
    master_resume: ResumeDocument, evidence: tuple[EvidenceItem, ...]
) -> tuple[_RoleSource, ...]:
    blocks = master_resume.blocks
    headings = [
        index
        for index, block in enumerate(blocks)
        if block.kind in {"heading_1", "heading_2", "heading_3"}
    ]
    roles = []
    for heading_position, start in enumerate(headings):
        end = headings[heading_position + 1] if heading_position + 1 < len(headings) else len(blocks)
        bullet_ids = tuple(
            evidence[index].id
            for index in range(start + 1, end)
            if blocks[index].kind in {"bulleted_list_item", "numbered_list_item"}
        )
        section_blocks = blocks[start:end]
        if bullet_ids and _is_work_experience_section(section_blocks):
            roles.append(
                _RoleSource(
                    heading_index=start,
                    end_index=end,
                    source_section=blocks[start].text,
                    evidence_ids=bullet_ids,
                )
            )
    return tuple(roles)


def _is_work_experience_section(
    section_blocks: tuple[DocumentBlock, ...]
    | list[DocumentBlock],
) -> bool:
    heading = _normalized(section_blocks[0].text)
    if heading in _NON_WORK_SECTION_NAMES:
        return False
    detail_text = " ".join(
        block.text
        for block in section_blocks[1:]
        if block.kind not in {"bulleted_list_item", "numbered_list_item"}
    )
    has_chronology = bool(
        re.search(r"\b(?:19|20)\d{2}\b", detail_text)
    )
    has_role_identity = bool(
        re.search(r"\b(?:at|with)\b|[,|]", section_blocks[0].text, re.IGNORECASE)
        or (has_chronology and re.search(r"[A-Za-z]", detail_text))
    )
    return has_chronology and has_role_identity


def _calculate_resume_fit_score(
    requirements: tuple[_RequirementPayload, ...],
    evidence: tuple[EvidenceItem, ...],
    matcher: EvidenceMatchingEngine,
) -> ResumeFitScore:
    requirement_fits = []
    weighted_score = 0.0
    total_weight = 0.0
    category_totals: dict[str, list[float]] = {}
    for requirement in requirements:
        matches = matcher.ranked_matches(requirement, evidence, limit=5)
        strongest = matches[0] if matches else EvidenceMatch(
            target_name=requirement.text,
            evidence_id=None,
            strength="no evidence",
            candidate_rank=0.0,
        )
        fit = RequirementFit(requirement, strongest, matches)
        requirement_fits.append(fit)
        weight = MATCHING_V1.weight_for(requirement)
        value = MATCHING_V1.strength_values[strongest.strength]
        weighted_score += weight * value
        total_weight += weight
        totals = category_totals.setdefault(requirement.category, [0.0, 0.0, 0.0])
        totals[0] += weight * value
        totals[1] += weight
        totals[2] += 1
    score = round(100 * weighted_score / total_weight) if total_weight else 0
    coverage = tuple(
        CategoryCoverage(
            category=category,
            score=round(100 * values[0] / values[1]) if values[1] else 0,
            requirement_count=int(values[2]),
        )
        for category, values in sorted(category_totals.items())
    )
    fits = tuple(requirement_fits)
    gaps = tuple(
        fit
        for fit in fits
        if fit.strongest.strength in {"weak evidence", "no evidence"}
    )
    supported = tuple(
        fit
        for fit in fits
        if fit.strongest.strength in {"direct evidence", "adjacent evidence"}
    )
    required = tuple(
        fit
        for fit in fits
        if fit.requirement.importance == "required"
        or fit.requirement.type in {"required skill", "responsibility"}
    )
    generation_allowed = bool(supported) and (
        not required or any(fit in supported for fit in required)
    )
    return ResumeFitScore(
        score=max(0, min(100, score)),
        requirements=fits,
        category_coverage=coverage,
        gaps=gaps,
        generation_allowed=generation_allowed,
        scoring_policy=SCORING_POLICY_VERSION,
    )


def _require_generation_evidence(fit_score: ResumeFitScore) -> None:
    if not fit_score.generation_allowed:
        raise ResumeEvidenceError(
            "Insufficient Master Resume evidence to create a truthful Job-Specific Resume."
        )


def _select_prompt_evidence(
    evidence: tuple[EvidenceItem, ...],
    roles: tuple[_RoleSource, ...],
    fit_score: ResumeFitScore,
) -> tuple[EvidenceItem, ...]:
    evidence_by_id = {item.id: item for item in evidence}
    supported_ids = {
        match.evidence_id
        for fit in fit_score.requirements
        if fit.strongest.strength in {"direct evidence", "adjacent evidence"}
        for match in fit.matches
        if match.evidence_id
        and match.strength in {"direct evidence", "adjacent evidence"}
    }
    selected: list[EvidenceItem] = []
    for role in roles:
        ranked_ids = [
            evidence_id
            for evidence_id in role.evidence_ids
            if evidence_id in supported_ids
        ]
        ranked_ids.extend(
            evidence_id
            for evidence_id in role.evidence_ids
            if evidence_id not in supported_ids
        )
        selected.extend(
            evidence_by_id[evidence_id] for evidence_id in ranked_ids[:7]
        )
    return tuple(selected)


def _validate_generated_resume(
    generated: _GeneratedResume,
    evidence: tuple[EvidenceItem, ...],
    roles: tuple[_RoleSource, ...],
    fit_score: ResumeFitScore,
    matcher: EvidenceMatchingEngine,
) -> None:
    evidence_by_id = {item.id: item for item in evidence}
    role_by_section = {role.source_section: role for role in roles}
    generated_by_section = {role.source_section: role for role in generated.roles}
    if len(generated_by_section) != len(generated.roles):
        raise ResumeModelOutputError("duplicate_role", "Generated roles must be unique.")
    if set(generated_by_section) != set(role_by_section):
        raise ResumeModelOutputError(
            "role_chronology", "Every Master Resume role must be preserved in order."
        )
    if [role.source_section for role in generated.roles] != [
        role.source_section for role in roles
    ]:
        raise ResumeModelOutputError(
            "role_chronology", "Master Resume role chronology must be preserved."
        )

    supported_requirement_ids = {
        fit.requirement.id
        for fit in fit_score.requirements
        if fit.strongest.strength in {"direct evidence", "adjacent evidence"}
    }
    for role in generated.roles:
        source = role_by_section[role.source_section]
        if len(source.evidence_ids) < 5 or not 5 <= len(role.bullets) <= 7:
            raise ResumeModelOutputError(
                "role_bullet_count",
                "Each work-experience role requires five to seven evidence-backed bullets.",
            )
        allowed_evidence = set(source.evidence_ids)
        for bullet in role.bullets:
            if not set(bullet.evidence_ids) <= allowed_evidence:
                raise ResumeModelOutputError(
                    "cross_role_claim", "Resume evidence must remain owned by its source role."
                )
            if not set(bullet.requirement_ids) <= supported_requirement_ids:
                raise ResumeModelOutputError(
                    "unsupported_requirement", "A bullet cited an unsupported requirement."
                )
            cited = tuple(evidence_by_id[item_id] for item_id in bullet.evidence_ids)
            if not _claim_supported(bullet.text, cited, matcher):
                raise ResumeModelOutputError(
                    "unsupported_claim", "A generated bullet was not supported by cited evidence."
                )


def _deterministically_complete_resume(
    generated: _GeneratedResume,
    master_resume: ResumeDocument,
    evidence: tuple[EvidenceItem, ...],
    roles: tuple[_RoleSource, ...],
    fit_score: ResumeFitScore,
    matcher: EvidenceMatchingEngine,
) -> _GeneratedResume:
    generated_by_section = {
        role.source_section: role for role in generated.roles
    }
    if set(generated_by_section) != {role.source_section for role in roles}:
        raise ResumeModelOutputError(
            "role_chronology", "Every Master Resume role must be preserved."
        )
    evidence_by_id = {item.id: item for item in evidence}
    supported_requirement_ids = {
        fit.requirement.id
        for fit in fit_score.requirements
        if fit.strongest.strength in {"direct evidence", "adjacent evidence"}
    }
    requirements_by_evidence: dict[str, list[str]] = {}
    for fit in fit_score.requirements:
        if fit.requirement.id not in supported_requirement_ids:
            continue
        for match in fit.matches:
            if match.evidence_id and match.strength in {
                "direct evidence",
                "adjacent evidence",
            }:
                requirements_by_evidence.setdefault(match.evidence_id, []).append(
                    fit.requirement.id
                )

    completed_roles = []
    for source in roles:
        source_role = generated_by_section[source.source_section]
        allowed = set(source.evidence_ids)
        bullets = []
        used_evidence: set[str] = set()
        for bullet in source_role.bullets:
            if (
                set(bullet.evidence_ids) <= allowed
                and set(bullet.requirement_ids) <= supported_requirement_ids
                and _claim_supported(
                    bullet.text,
                    tuple(evidence_by_id[item_id] for item_id in bullet.evidence_ids),
                    matcher,
                )
            ):
                bullets.append(bullet)
                used_evidence.update(bullet.evidence_ids)
        target_count = min(6, len(source.evidence_ids))
        for evidence_id in source.evidence_ids:
            if len(bullets) >= target_count or len(bullets) >= 7:
                break
            if evidence_id in used_evidence:
                continue
            item = evidence_by_id[evidence_id]
            bullets.append(
                _GeneratedBullet(
                    text=item.text,
                    evidenceIds=[evidence_id],
                    requirementIds=requirements_by_evidence.get(evidence_id, [])[:3],
                )
            )
            used_evidence.add(evidence_id)
        if len(bullets) < 5:
            raise ResumeModelOutputError(
                "role_bullet_count",
                f'Role "{source.source_section}" could not reach five truthful bullets.',
            )
        completed_roles.append(
            _GeneratedRole(
                sourceSection=source.source_section,
                bullets=bullets[:7],
            )
        )

    summary = generated.summary
    if not _claim_supported(summary, evidence, matcher):
        summary = _master_summary(master_resume) or evidence[0].text
    return _GeneratedResume(summary=summary, roles=completed_roles)


def _master_summary(master_resume: ResumeDocument) -> str | None:
    in_summary = False
    for block in master_resume.blocks:
        if block.kind in {"heading_1", "heading_2", "heading_3"}:
            if in_summary:
                return None
            in_summary = _normalized(block.text) == "summary"
            continue
        if in_summary and block.text.strip():
            return block.text.strip()
    return None


def _claim_supported(
    claim: str, evidence: tuple[EvidenceItem, ...], matcher: EvidenceMatchingEngine
) -> bool:
    normalized_claim = _normalized(claim)
    if any(normalized_claim == _normalized(item.text) for item in evidence):
        return True
    evidence_text = " ".join(item.text for item in evidence)
    normalized_evidence = _normalized(evidence_text)
    claim_numbers = set(re.findall(r"(?<!\w)\d+(?:[.,]\d+)?%?", claim))
    evidence_numbers = set(
        re.findall(r"(?<!\w)\d+(?:[.,]\d+)?%?", evidence_text)
    )
    if not claim_numbers <= evidence_numbers:
        return False
    ownership_terms = {
        "architected",
        "directed",
        "headed",
        "led",
        "managed",
        "owned",
        "oversaw",
        "supervised",
    }
    claim_terms = set(normalized_claim.split())
    evidence_terms = set(normalized_evidence.split())
    if (claim_terms & ownership_terms) - evidence_terms:
        return False
    proper_nouns = {
        token.casefold()
        for index, token in enumerate(re.findall(r"\b[A-Z][A-Za-z0-9.+#-]*\b", claim))
        if index > 0 or token.isupper()
    }
    if proper_nouns - evidence_terms:
        return False
    stopwords = {
        "a", "an", "and", "as", "at", "by", "for", "from", "in", "of",
        "on", "or", "that", "the", "to", "using", "with", "who",
    }

    def lexemes(value: str) -> set[str]:
        words = re.findall(r"[a-z0-9+#.]+", value.casefold())
        return {
            re.sub(r"(?:ing|ed|es|s)$", "", word)
            for word in words
            if word not in stopwords and len(word) > 2
        }

    # Generated claims may compress source wording, but every substantive term
    # must still have provenance in the cited source. This deliberately favors
    # truthful source bullets over an unsupported fluent paraphrase.
    if not lexemes(claim) <= lexemes(evidence_text):
        return False
    target = _RequirementPayload(
        id="claim",
        text=claim,
        type="responsibility",
        category="Claim",
        importance="required",
        evidence=claim,
    )
    result = matcher.match((target,), evidence, MATCHING_V1)
    return result.matches[0].strength in {"direct evidence", "adjacent evidence"}


def _render_resume_document(
    master_resume: ResumeDocument,
    generated: _GeneratedResume,
    roles: tuple[_RoleSource, ...],
) -> tuple[DocumentBlock, ...]:
    role_by_start = {role.heading_index: role for role in roles}
    generated_by_section = {role.source_section: role for role in generated.roles}
    output: list[DocumentBlock] = []
    index = 0
    while index < len(master_resume.blocks):
        block = master_resume.blocks[index]
        role = role_by_start.get(index)
        if role:
            output.append(block)
            for source_block in master_resume.blocks[index + 1 : role.end_index]:
                if source_block.kind not in {"bulleted_list_item", "numbered_list_item"}:
                    output.append(source_block)
            output.extend(
                DocumentBlock(kind="bulleted_list_item", text=bullet.text)
                for bullet in generated_by_section[role.source_section].bullets
            )
            index = role.end_index
            continue
        if block.kind in {"heading_1", "heading_2", "heading_3"} and _normalized(block.text) == "summary":
            output.append(block)
            index += 1
            while index < len(master_resume.blocks) and master_resume.blocks[index].kind not in {
                "heading_1",
                "heading_2",
                "heading_3",
            }:
                index += 1
            output.append(DocumentBlock(kind="paragraph", text=generated.summary))
            continue
        output.append(block)
        index += 1
    return tuple(output)


def _render_fit_note(
    application: ApplicationRecord,
    fit_score: ResumeFitScore,
    generated: _GeneratedResume,
) -> tuple[DocumentBlock, ...]:
    blocks = [
        DocumentBlock(kind="heading_2", text="Resume Fit Analysis"),
        DocumentBlock(kind="heading_3", text="Summary"),
        DocumentBlock(
            kind="paragraph",
            text=(
                f"Evidence-grounded comparison for {application.role} at "
                f"{application.company_name}."
            ),
        ),
        DocumentBlock(kind="heading_3", text="Fit Score"),
        DocumentBlock(
            kind="paragraph",
            text=f"{fit_score.score}% using {fit_score.scoring_policy}.",
        ),
        DocumentBlock(kind="heading_3", text="Category Coverage"),
        *(
            DocumentBlock(
                kind="bulleted_list_item",
                text=(
                    f"{category.category}: {category.score}% across "
                    f"{category.requirement_count} requirement(s)"
                ),
            )
            for category in fit_score.category_coverage
        ),
        DocumentBlock(kind="heading_3", text="Requirement Evidence Map"),
    ]
    for fit in fit_score.requirements:
        blocks.append(
            DocumentBlock(
                kind="bulleted_list_item",
                text=(
                    f"{fit.requirement.id}: {fit.requirement.text} — "
                    f"{fit.strongest.strength}"
                ),
            )
        )
        for match in fit.matches:
            blocks.append(
                DocumentBlock(
                    kind="bulleted_list_item",
                    text=f"Evidence: {match.evidence_id or 'none'} — {match.strength}",
                    depth=1,
                )
            )
    blocks.append(DocumentBlock(kind="heading_3", text="Gaps"))
    if fit_score.gaps:
        blocks.extend(
            DocumentBlock(
                kind="bulleted_list_item",
                text=f"{gap.requirement.id}: {gap.requirement.text} — {gap.strongest.strength}",
            )
            for gap in fit_score.gaps
        )
    else:
        blocks.append(
            DocumentBlock(
                kind="bulleted_list_item",
                text="No weak or unsupported Fit Requirements were identified.",
            )
        )
    blocks.append(DocumentBlock(kind="heading_3", text="Final Claim Traces"))
    for role in generated.roles:
        for index, bullet in enumerate(role.bullets, start=1):
            blocks.append(
                DocumentBlock(
                    kind="bulleted_list_item",
                    text=(
                        f"{role.source_section} bullet {index}: Evidence "
                        f"{', '.join(bullet.evidence_ids)}; Requirements "
                        f"{', '.join(bullet.requirement_ids) or 'none'}"
                    ),
                )
            )
    blocks.extend(
        (
            DocumentBlock(kind="heading_3", text="Generation Guardrails"),
            DocumentBlock(
                kind="bulleted_list_item",
                text="Every work-experience role and its chronology were preserved.",
            ),
            DocumentBlock(
                kind="bulleted_list_item",
                text="Only direct or adjacent evidence supported job-specific claims.",
            ),
        )
    )
    return tuple(blocks)


def _resume_input(
    application: ApplicationRecord,
    evidence: tuple[EvidenceItem, ...],
    roles: tuple[_RoleSource, ...],
    fit_score: ResumeFitScore,
) -> ResumeDraftInput:
    supported_fits = [
        fit
        for fit in fit_score.requirements
        if fit.strongest.strength in {"direct evidence", "adjacent evidence"}
    ]
    return ResumeDraftInput(
        target=application.title,
        supportedRequirements=[
            {
                "id": fit.requirement.id,
                "text": fit.requirement.text,
                "type": fit.requirement.type,
                "category": fit.requirement.category,
                "importance": fit.requirement.importance,
                "evidence": fit.requirement.evidence,
                "strength": fit.strongest.strength,
                "evidenceIds": [
                    match.evidence_id
                    for match in fit.matches
                    if match.evidence_id
                    and match.strength in {"direct evidence", "adjacent evidence"}
                ],
            }
            for fit in supported_fits
        ],
        fitScore=fit_score.score,
        categoryCoverage=[
            {
                "category": category.category,
                "score": category.score,
                "requirementCount": category.requirement_count,
            }
            for category in fit_score.category_coverage
        ],
        roleTargets=[
            _PromptRoleTarget(
                sourceSection=role.source_section,
                evidenceIds=[
                    item.id
                    for item in evidence
                    if item.id in role.evidence_ids
                ],
                minimumBullets=5,
                preferredBullets=6,
                maximumBullets=7,
            )
            for role in roles
        ],
        evidenceItems=[
            _PromptEvidenceItem(
                id=item.id,
                text=item.text,
                sourceSection=item.source_section,
            )
            for item in evidence
        ],
    )


def _source_contains(source: str, evidence: str) -> bool:
    return bool(_normalized(evidence) and _normalized(evidence) in _normalized(source))


def _normalize_requirement_importance(
    requirement: _RequirementPayload, job_content: str
) -> _RequirementPayload:
    if requirement.importance == "required":
        return requirement
    evidence = _normalized(requirement.evidence)
    current_heading = ""
    for raw_line in job_content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        normalized = _normalized(line)
        if len(line) <= 100 and any(
            marker in normalized
            for marker in (
                "responsibilities",
                "requirements",
                "required qualifications",
                "minimum qualifications",
                "preferred qualifications",
                "nice to have",
                "what you will do",
            )
        ):
            current_heading = normalized
        if evidence and evidence in normalized:
            preferred_context = any(
                marker in current_heading
                for marker in ("preferred qualifications", "nice to have")
            )
            if not preferred_context and any(
                marker in current_heading
                for marker in (
                    "responsibilities",
                    "requirements",
                    "required qualifications",
                    "minimum qualifications",
                    "what you will do",
                )
            ):
                return requirement.model_copy(update={"importance": "required"})
            if requirement.importance == "signal" and preferred_context:
                return requirement.model_copy(update={"importance": "preferred"})
            break
    return requirement


def _normalized(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9+#.]+", " ", str(value).lower()).split())
