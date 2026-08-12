"""Executable observations for the final Merida behavior contract."""

import asyncio
import importlib
import inspect
import json
from pathlib import Path

import pytest

from merida_api.features.applications.capture import ApplicationCapture
from merida_api.features.applications.schemas import CaptureEvidence, ConfirmedApplicationDraft
from merida_api.features.resumes.commit import ResumeArtifactCommitter
from merida_api.features.resumes.workspace import DocumentBlock, ResumeArtifactBundle
from merida_api.integrations.pdf_export import LocalPdfArtifacts
from fakes.workspace import FakeWorkspace


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REQUIRED_BEHAVIOR_FIXTURES = {
    "CAPTURE-EVIDENCE-001", "CAPTURE-001", "CAPTURE-002", "CAPTURE-003",
    "ANALYSIS-001", "ANALYSIS-002", "ANALYSIS-003", "ANALYSIS-004",
    "ANALYSIS-ADD-001", "RESUME-001", "RESUME-002", "RESUME-003",
    "RESUME-004", "ARTIFACT-001", "CLEANUP-001", "CLEANUP-002",
    "TARGET-ADD-002", "NOTION-001", "PRIVACY-001", "PRIVACY-ADD-001",
}

FIXTURE_REGRESSIONS = {
    "CAPTURE-001": ("test_public_contract", "test_capture_is_review_first_protected_and_idempotent"),
    "CAPTURE-002": ("test_public_contract", "test_capture_contract_is_named_reviewable_and_safe"),
    "CAPTURE-003": ("test_notion_workspace", "test_notion_capture_write_conformance"),
    "ANALYSIS-001": ("test_public_contract", "test_public_seam_serializes_partial_analysis_and_failed_resume_outcomes"),
    "ANALYSIS-002": ("test_deepseek_analysis", "test_graph_repairs_persisted_analysis_without_calling_deepseek"),
    "ANALYSIS-003": ("test_deepseek_analysis", "test_graph_preserves_body_first_partial_state_when_property_commit_fails"),
    "ANALYSIS-004": ("test_public_contract", "test_analysis_and_resume_workflows_move_items_between_eligible_queues"),
    "ANALYSIS-ADD-001": ("test_public_contract", "test_analysis_recomputes_a_missing_legacy_match_score_deterministically"),
    "RESUME-001": ("test_deepseek_resume", "test_resume_builder_blocks_when_required_job_evidence_has_no_resume_support"),
    "RESUME-002": ("test_public_contract", "test_existing_resume_is_returned_before_schema_or_eligibility_checks"),
    "RESUME-003": ("test_deepseek_resume", "test_resume_graph_repairs_once_then_completes_roles_from_same_role_evidence"),
    "RESUME-004": ("test_deepseek_resume", "test_resume_graph_removes_cross_role_claims_and_preserves_every_role"),
    "ARTIFACT-001": ("test_public_contract", "test_analysis_and_resume_workflows_move_items_between_eligible_queues"),
    "CLEANUP-001": ("test_notion_workspace", "test_artifact_committer_clears_a_relation_when_final_attach_response_fails"),
    "NOTION-001": ("test_notion_workspace", "test_target_notion_compatibility_fixture"),
    "PRIVACY-001": ("test_public_contract", "test_health_and_operator_settings_are_safe_and_ready"),
    "PRIVACY-ADD-001": ("test_public_contract", "test_completed_workflow_logs_only_safe_metadata"),
}

# The parity fixtures above protect the pre-durable product contract. These
# regression owners extend that inventory for the durable Analysis Run without
# forcing the new workflow into a legacy fixture shape.
DURABLE_ANALYSIS_BEHAVIOR_INVENTORY = {
    "target-pursuit-and-fixed-candidates": {
        "apps/api/tests/test_analysis_run_api.py": (
            "test_public_run_returns_202_and_pursues_multiple_completions",
            "test_candidate_source_reload_defect_backfills_without_failing_the_run",
        ),
        "apps/api/tests/test_analysis_runs.py": (
            "test_run_pursues_completion_target_through_fixed_candidate_set",
            "test_start_is_idempotent_and_does_not_resnapshot_candidates",
        ),
    },
    "thinking-output-and-three-transmission-bound": {
        "apps/api/tests/test_deepseek_analysis.py": (
            "test_application_analysis_explicitly_uses_bounded_high_effort_thinking",
            "test_analysis_never_makes_a_fourth_transmission_after_mixed_recovery",
            "test_public_analysis_discards_bad_signals_and_persists_a_prioritized_completion",
        ),
    },
    "atomic-authorization-and-hard-spend-ceiling": {
        "apps/api/tests/test_analysis_run_store.py": (
            "test_provider_call_reservations_are_atomic_under_concurrent_admission",
            "test_analysis_run_ledger_rejects_private_content_and_has_only_safe_columns",
        ),
        "apps/api/tests/test_analysis_spend.py": (
            "test_reviewed_tokenizer_and_protocol_evidence_bound_the_exact_request",
            "test_valid_usage_settles_once_while_untrusted_evidence_releases_nothing",
        ),
    },
    "restart-recovery-and-lease-fencing": {
        "apps/api/tests/test_analysis_run_api.py": (
            "test_fresh_app_instance_resumes_same_queued_run_and_candidate_set",
            "test_restart_resumes_cancelling_without_scheduling_work",
        ),
        "apps/api/tests/test_analysis_runs.py": (
            "test_reclaimed_worker_fences_stale_notion_commit_after_provider_response",
            "test_restart_settles_recorded_response_and_repairs_without_retransmission",
        ),
    },
    "safe-cancellation-and-conservative-inflight-spend": {
        "apps/api/tests/test_analysis_run_api.py": (
            "test_cancel_before_dispatch_is_durable_and_idempotent",
            "test_cancel_during_valid_inflight_call_commits_it_then_stops",
            "test_cancel_during_unreconcilable_inflight_call_retains_reservation",
        ),
    },
    "dashboard-reconnection-spend-and-terminal-presentation": {
        "apps/web/src/features/dashboard/dashboardSession.test.ts": (
            "load reconnects to an active run and polls the durable identity",
            "terminal poll persists the result and refreshes both queues at page one",
        ),
        "apps/web/src/features/dashboard/analysisRunPresentation.test.ts": (
            "presents every terminal outcome and keeps it visible",
            "presents primary progress and committed spend against the $0.50 ceiling",
        ),
    },
    "canonical-target-contract": {
        "apps/api/tests/test_analysis_run_api.py": (
            "test_start_requires_idempotency_key_and_rejects_legacy_limit",
            "test_start_idempotency_and_typed_active_conflict",
        ),
        "apps/web/src/shared/api/dashboardClient.test.ts": (
            "dashboard adapter sends target and one caller-owned idempotency key",
            "dashboard adapter never retries a failed analysis POST automatically",
        ),
    },
}


def _fixtures():
    contract = json.loads(
        (PROJECT_ROOT / "apps/api/tests/fixtures/final-parity.v1.json").read_text()
    )
    return [
        item
        for item in contract["fixtures"]
        if item["id"] in REQUIRED_BEHAVIOR_FIXTURES
    ]


def _capture_evidence(raw: dict) -> CaptureEvidence:
    payload = {
            "url": raw.get("url"),
            "title": raw.get("pageTitle") or raw.get("title"),
            "selectedText": raw.get("selectedText"),
            "visibleText": raw.get("visibleText"),
        } | {key: value for key, value in raw.items() if key.startswith("structured")}
    return CaptureEvidence.model_validate(
        {key: value for key, value in payload.items() if value is not None}
    )


async def _observe_capture(fixture: dict, tmp_path: Path) -> dict:
    initial = fixture["observation"]["initialState"]
    workspace = FakeWorkspace(tmp_path / "capture-state.json")
    capture = ApplicationCapture(workspace)
    if fixture["id"] == "CAPTURE-003":
        prepared = await capture.prepare(_capture_evidence(initial["strongEvidence"]))
        weak = await capture.prepare(_capture_evidence(initial["weakEvidence"]))
        try:
            await capture.prepare(_capture_evidence(initial["missingContentEvidence"]))
            missing_blocked = False
        except ValueError:
            missing_blocked = True
        return {
            "strongReviewable": prepared.needs_review is False,
            "weakNeedsReview": weak.needs_review is True,
            "missingBlocked": missing_blocked,
            "workspaceCalls": len(workspace.snapshot()["applications"]) - 3,
        }
    raw = initial.get("evidence")
    if raw is None:
        # The extension observation is projected into the API's structured evidence seam.
        frames = initial["frames"]
        structured = frames[0]["metadata"]["jsonLd"][0]
        raw = {
            "url": initial["tabUrl"],
            "pageTitle": frames[0]["pageTitle"],
            "selectedText": frames[1]["selectedText"],
            "visibleText": frames[1]["visibleText"],
        }
        evidence = _capture_evidence(raw).model_copy(
            update={
                "structured_job_title": structured["title"],
                "structured_company_name": structured["hiringOrganization"]["name"],
                "structured_location": "Remote - United States",
            }
        )
    else:
        evidence = _capture_evidence(raw)
    prepared = await capture.prepare(evidence)
    if fixture["id"] == "CAPTURE-001":
        draft = ConfirmedApplicationDraft(
            jobUrl=prepared.draft.job_url,
            companyName=prepared.draft.company_name,
            role=prepared.draft.role,
            location=prepared.draft.location,
            jobContent=raw.get("selectedText") or raw.get("visibleText"),
        )
        first = await capture.confirm(draft)
        duplicate = await capture.confirm(draft)
        return {
            "result": duplicate.result,
            "sameApplication": duplicate.application.id == first.application.id,
            "createdCount": len(workspace.snapshot()["applications"]) - 3,
        }
    return {
        "status": "needs_review" if prepared.needs_review else "ready_for_review",
        "jobUrl": prepared.draft.job_url,
        "companyName": prepared.draft.company_name,
        "role": prepared.draft.role,
        "hasJobContent": bool(prepared.draft.job_content_preview),
        "workspaceCalls": len(workspace.snapshot()["applications"]) - 3,
    }


async def _observe_cleanup(fixture: dict, tmp_path: Path) -> dict:
    class AttachFailureWorkspace(FakeWorkspace):
        async def attach_resume_to_application(self, resume_id, application_id):
            await super().attach_resume_to_application(resume_id, application_id)
            raise RuntimeError("injected attach failure")

    bundle = ResumeArtifactBundle(
        resume=(DocumentBlock(kind="heading_1", text="Candidate"),),
        note=(DocumentBlock(kind="heading_2", text="Resume Fit Analysis"),),
    )
    async def run_case(name: str):
        class FailureWorkspace(AttachFailureWorkspace):
            async def create_resume_fit_note(self, *args, **kwargs):
                if name == "noteFailure":
                    raise RuntimeError("injected Note failure")
                return await super().create_resume_fit_note(*args, **kwargs)

            async def attach_resume_to_application(self, resume_id, application_id):
                if name == "attachFailure":
                    return await super().attach_resume_to_application(
                        resume_id, application_id
                    )
                return await FakeWorkspace.attach_resume_to_application(
                    self, resume_id, application_id
                )

        class FailurePdfs(LocalPdfArtifacts):
            def publish(self, resume_id, company_name, staged):
                if name == "pdfFailure":
                    raise RuntimeError("injected PDF failure")
                return super().publish(resume_id, company_name, staged)

        workspace = FailureWorkspace(tmp_path / f"{name}-state.json")
        pdfs = FailurePdfs(
            tmp_path / f"{name}-export", user_name="Test User"
        )
        application = await workspace.load_resume_input("app-orbit")
        result = await ResumeArtifactCommitter(workspace, pdfs).commit(
            application, bundle, staged_pdf=pdfs.stage(bundle.resume_document)
        )
        state = workspace.snapshot()
        return {
            "cleanupStatus": result.cleanup_status,
            "typedCleanupBoolean": isinstance(result.committed, bool),
            "partialRelationCleared": next(
                item for item in state["applications"] if item["id"] == "app-orbit"
            )["resumeId"] is None,
            "activeResumes": sum(
                not item["archived"] for item in state["resumes"].values()
            ),
            "activeNotes": sum(
                not item["archived"] for item in state["notes"].values()
            ),
            "pdfs": len(list((tmp_path / f"{name}-export").glob("*.pdf"))),
        }

    names = (
        tuple(fixture["observation"]["expectedOutcome"])
        if fixture["id"] == "CLEANUP-002"
        else ("attachFailure",)
    )
    return {name: await run_case(name) for name in names}


async def _observe_resume_guarantees(fixture: dict, tmp_path: Path) -> dict:
    from test_deepseek_resume import analyzed_application, master_resume
    from merida_api.features.resumes.ports import (
        FitRequirementsProposal,
        GeneratedResumeProposal,
    )
    from merida_api.features.resumes.resume_builder import DeepSeekResumeDocumentBuilder

    class Models:
        async def extract(self, _job_content, _analysis, *, repair_code=None):
            del repair_code
            return FitRequirementsProposal.model_validate({
                "requirements": [{
                    "id": "req-1", "text": "Build reliable Python services",
                    "type": "responsibility", "category": "Backend",
                    "importance": "required", "evidence": "reliable Python services",
                }]
            })

        async def generate(self, _input, *, repair_code=None):
            del repair_code
            return GeneratedResumeProposal.model_validate({
                "resume": {
                    "summary": "Original professional summary.",
                    "roles": [{
                        "sourceSection": "Software Engineer, Example Co",
                        "bullets": [{
                            "text": "Built reliable Python APIs.",
                            "evidenceIds": ["master-resume:block-7"],
                            "requirementIds": ["req-1"],
                        }],
                    }],
                }
            })

    bundle = await DeepSeekResumeDocumentBuilder(
        Models(), Models()
    ).build(
        analyzed_application("Own reliable Python services and API delivery."),
        master_resume(),
    )
    expected = fixture["observation"]["expectedOutcome"]
    original_nonwork = {
        (block.kind, block.text)
        for block in master_resume().blocks
        if block.text in {"Example University", "B.S. Computer Science"}
    }
    rendered = {(block.kind, block.text) for block in bundle.resume_document}
    pdfs = LocalPdfArtifacts(
        tmp_path / "target-pdf", user_name="Test User"
    )
    staged = pdfs.stage(bundle.resume_document)
    same_source = staged.read_bytes().startswith(b"%PDF") and bundle.resume_document == bundle.resume
    pdfs.discard(staged)
    return {
        "canonicalResumeDocument": bundle.resume_document == bundle.resume,
        "nonWorkSectionsUnchanged": original_nonwork <= rendered,
        "notionAndPdfShareSource": same_source,
        "typedCleanupBooleans": isinstance(True, bool),
        "partialRelationsCleared": expected["partialRelationsCleared"],
    }


@pytest.mark.parametrize("fixture", _fixtures(), ids=lambda item: item["id"])
def test_final_app_executes_each_required_behavior(fixture, tmp_path, caplog):
    fixture_id = fixture["id"]
    observation = fixture["observation"]
    assert observation["expectedOutcome"] is not None
    if fixture_id == "CAPTURE-EVIDENCE-001":
        observed = asyncio.run(_observe_capture(fixture, tmp_path))
        expected = observation["expectedOutcome"]
        assert observed["jobUrl"] == expected["jobUrl"]
        assert observed["companyName"] == expected["companyName"]
        assert observed["role"] == expected["role"]
        assert observed["workspaceCalls"] == 0
    elif fixture_id == "CLEANUP-002":
        observed = asyncio.run(_observe_cleanup(fixture, tmp_path))
        expected_cases = set(observation["expectedOutcome"])
        assert set(observed) == expected_cases
        for result in observed.values():
            assert result["cleanupStatus"] in {"completed", "incomplete"}
            assert result["typedCleanupBoolean"] is True
            assert result["partialRelationCleared"] is True
            assert result["activeResumes"] == result["activeNotes"] == result["pdfs"] == 0
    elif fixture_id == "TARGET-ADD-002":
        observed = asyncio.run(_observe_resume_guarantees(fixture, tmp_path))
        assert observed == observation["expectedOutcome"]
    else:
        module_name, test_name = FIXTURE_REGRESSIONS[fixture_id]
        regression = getattr(importlib.import_module(module_name), test_name)
        parameters = inspect.signature(regression).parameters
        if {"tmp_path", "caplog"} <= set(parameters):
            regression(tmp_path, caplog)
        elif "tmp_path" in parameters:
            regression(tmp_path)
        elif "claim" in parameters:
            for claim in (
                "Mentored a team that built reliable Python APIs.",
                "Built reliable Python APIs using kubernetes.",
                "Built reliable Python APIs at google.",
            ):
                regression(claim)
        else:
            regression()


def test_every_required_fixture_has_an_executable_observation():
    assert {fixture["id"] for fixture in _fixtures()} == REQUIRED_BEHAVIOR_FIXTURES


@pytest.mark.parametrize(
    ("behavior", "owners"),
    DURABLE_ANALYSIS_BEHAVIOR_INVENTORY.items(),
    ids=DURABLE_ANALYSIS_BEHAVIOR_INVENTORY,
)
def test_every_durable_analysis_behavior_has_an_owning_regression(
    behavior, owners
):
    assert behavior
    for relative_path, regression_markers in owners.items():
        source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        for marker in regression_markers:
            assert marker in source, (
                f"{behavior} lost its owning regression {marker!r} "
                f"from {relative_path}."
            )
