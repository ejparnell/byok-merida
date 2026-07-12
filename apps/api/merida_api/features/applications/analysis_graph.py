from dataclasses import dataclass
from typing import Literal, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from .ports import ApplicationAnalysisModel, ApplicationAnalysisStore
from .analysis_model import AnalysisModelOutputError, validate_analysis_payload
from .workspace import (
    AnalysisModelResponse,
    ApplicationAnalysisDocument,
    ApplicationAnalysisDraft,
    ApplicationRecord,
    PersistedSkillSignal,
    SkillSignal,
)
from ...matching import (
    MATCHING_V1,
    EvidenceItem,
    EvidenceMatchingEngine,
    MatchingResult,
)


AnalysisItemResult = Literal["analyzed", "repaired", "skipped", "failed"]


@dataclass(frozen=True)
class AnalysisGraphOutcome:
    application: ApplicationRecord
    result: AnalysisItemResult
    match_score: int | None
    errors: tuple[str, ...] = ()


class _AnalysisState(TypedDict, total=False):
    batch_run_id: str
    run_id: str
    workflow: Literal["application_analysis"]
    application_id: str
    application: ApplicationRecord
    analysis_attempt: int
    model_response: AnalysisModelResponse
    validation_error: str
    terminal_error: bool
    draft: ApplicationAnalysisDraft
    evidence: tuple[EvidenceItem, ...]
    matching: MatchingResult
    document: ApplicationAnalysisDocument
    repair_score: int | None
    match_score: int
    commit_stage: Literal["none", "body_appended", "properties_committed"]
    errors: tuple[str, ...]
    outcome: AnalysisGraphOutcome


class ApplicationAnalysisGraph:
    def __init__(
        self,
        store: ApplicationAnalysisStore,
        model: ApplicationAnalysisModel,
        matcher: EvidenceMatchingEngine,
    ):
        self._store = store
        self._model = model
        self._matcher = matcher
        self._graph = self._build_graph()

    async def run(
        self, application: ApplicationRecord, *, batch_run_id: str
    ) -> AnalysisGraphOutcome:
        try:
            state = await self._graph.ainvoke(
                {
                    "batch_run_id": batch_run_id,
                    "run_id": f"analysis-{uuid4().hex}",
                    "workflow": "application_analysis",
                    "application_id": application.id,
                    "application": application,
                    "analysis_attempt": 0,
                    "commit_stage": "none",
                    "errors": (),
                }
            )
            return state["outcome"]
        except Exception:
            return AnalysisGraphOutcome(
                application=application,
                result="failed",
                match_score=None,
                errors=("Application Analysis failed for this item.",),
            )

    def _build_graph(self):
        graph = StateGraph(_AnalysisState)
        graph.add_node("load_and_revalidate_application", self._load_application)
        graph.add_node("inspect_existing_analysis", self._inspect_existing)
        graph.add_node("skip_ineligible", self._skip_ineligible)
        graph.add_node("repair_analysis_properties", self._repair_properties)
        graph.add_node("load_master_resume_evidence", self._load_evidence)
        graph.add_node("call_analysis_model", self._call_model)
        graph.add_node("validate_analysis_output", self._validate_output)
        graph.add_node("fail_analysis", self._fail_analysis)
        graph.add_node("match_skill_signals", self._match_signals)
        graph.add_node("calculate_match_score", self._calculate_score)
        graph.add_node("render_application_analysis", self._render_analysis)
        graph.add_node("append_analysis_body", self._append_body)
        graph.add_node("commit_match_score_and_analyzed", self._commit_properties)
        graph.add_node("complete_analysis", self._complete_analysis)
        graph.add_node("complete_repair", self._complete_repair)

        graph.add_edge(START, "load_and_revalidate_application")
        graph.add_edge("load_and_revalidate_application", "inspect_existing_analysis")
        graph.add_conditional_edges(
            "inspect_existing_analysis",
            self._route_after_inspection,
            {
                "skip": "skip_ineligible",
                "repair": "repair_analysis_properties",
                "analyze": "load_master_resume_evidence",
            },
        )
        graph.add_edge("skip_ineligible", END)
        graph.add_edge("repair_analysis_properties", "complete_repair")
        graph.add_edge("complete_repair", END)
        graph.add_edge("load_master_resume_evidence", "call_analysis_model")
        graph.add_edge("call_analysis_model", "validate_analysis_output")
        graph.add_conditional_edges(
            "validate_analysis_output",
            self._route_after_validation,
            {
                "repair": "call_analysis_model",
                "valid": "match_skill_signals",
                "failed": "fail_analysis",
            },
        )
        graph.add_edge("fail_analysis", END)
        graph.add_edge("match_skill_signals", "calculate_match_score")
        graph.add_edge("calculate_match_score", "render_application_analysis")
        graph.add_edge("render_application_analysis", "append_analysis_body")
        graph.add_edge("append_analysis_body", "commit_match_score_and_analyzed")
        graph.add_edge("commit_match_score_and_analyzed", "complete_analysis")
        graph.add_edge("complete_analysis", END)
        return graph.compile()

    async def _load_application(self, state: _AnalysisState) -> dict:
        return {
            "application": await self._store.load_analysis_input(
                state["application_id"]
            )
        }

    async def _inspect_existing(self, state: _AnalysisState) -> dict:
        return {}

    def _route_after_inspection(self, state: _AnalysisState) -> str:
        application = state["application"]
        if (
            application.application_status != "To Apply"
            or application.analyzed
            or len((application.job_content or "").strip()) < 20
        ):
            return "skip"
        return "repair" if application.analysis is not None else "analyze"

    async def _skip_ineligible(self, state: _AnalysisState) -> dict:
        return {
            "outcome": AnalysisGraphOutcome(
                application=state["application"],
                result="skipped",
                match_score=state["application"].match_score,
                errors=("Job Posting is no longer eligible for Analysis.",),
            )
        }

    async def _repair_properties(self, state: _AnalysisState) -> dict:
        application = state["application"]
        analysis = application.analysis
        assert analysis is not None
        score = (
            analysis.match_score
            if analysis.match_score is not None
            else application.match_score
        )
        if score is None:
            evidence = await self._store.load_analysis_evidence()
            legacy_signals = tuple(
                SkillSignal(
                    name=signal.name,
                    category="other",
                    importance="signal",
                    evidence=signal.name,
                )
                for signal in analysis.skill_signals
                if signal.name.strip()
            )
            if legacy_signals and evidence:
                score = self._matcher.match(
                    legacy_signals, evidence, MATCHING_V1
                ).score
        await self._store.finalize_application_analysis(
            application.id, match_score=score
        )
        return {"document": analysis, "repair_score": score}

    async def _complete_repair(self, state: _AnalysisState) -> dict:
        return {
            "outcome": AnalysisGraphOutcome(
                application=state["application"],
                result="repaired",
                match_score=state["repair_score"],
            )
        }

    async def _load_evidence(self, state: _AnalysisState) -> dict:
        return {"evidence": await self._store.load_analysis_evidence()}

    async def _call_model(self, state: _AnalysisState) -> dict:
        attempt = state.get("analysis_attempt", 0) + 1
        try:
            response = await self._model.generate(
                state["application"],
                repair_code=state.get("validation_error"),
            )
            return {
                "analysis_attempt": attempt,
                "model_response": response,
                "terminal_error": False,
            }
        except Exception:
            return {
                "analysis_attempt": attempt,
                "validation_error": "provider_error",
                "terminal_error": True,
                "errors": ("Application Analysis model call failed.",),
            }

    async def _validate_output(self, state: _AnalysisState) -> dict:
        if state.get("terminal_error"):
            return {}
        response = state["model_response"]
        if response.error_code:
            return {"validation_error": response.error_code}
        try:
            draft = validate_analysis_payload(
                response.payload or {}, state["application"].job_content or ""
            )
        except AnalysisModelOutputError as error:
            return {"validation_error": error.code}
        return {"draft": draft, "validation_error": ""}

    def _route_after_validation(self, state: _AnalysisState) -> str:
        if not state.get("validation_error"):
            return "valid"
        if not state.get("terminal_error") and state["analysis_attempt"] < 2:
            return "repair"
        return "failed"

    async def _fail_analysis(self, state: _AnalysisState) -> dict:
        return {
            "outcome": AnalysisGraphOutcome(
                application=state["application"],
                result="failed",
                match_score=None,
                errors=state.get("errors")
                or ("Application Analysis output failed validation.",),
            )
        }

    async def _match_signals(self, state: _AnalysisState) -> dict:
        return {
            "matching": self._matcher.match(
                state["draft"].skill_signals,
                state["evidence"],
                MATCHING_V1,
            )
        }

    async def _calculate_score(self, state: _AnalysisState) -> dict:
        return {"match_score": state["matching"].score}

    async def _render_analysis(self, state: _AnalysisState) -> dict:
        return {
            "document": ApplicationAnalysisDocument(
                summary=" ".join(state["draft"].summary),
                match_score=state["match_score"],
                skill_signals=tuple(
                    PersistedSkillSignal.from_signal(signal)
                    for signal in state["draft"].skill_signals
                ),
                heading="Application Analysis",
            )
        }

    async def _append_body(self, state: _AnalysisState) -> dict:
        await self._store.append_application_analysis(
            state["application"].id, state["document"]
        )
        return {"commit_stage": "body_appended"}

    async def _commit_properties(self, state: _AnalysisState) -> dict:
        await self._store.finalize_application_analysis(
            state["application"].id,
            match_score=state["document"].match_score,
        )
        return {"commit_stage": "properties_committed"}

    async def _complete_analysis(self, state: _AnalysisState) -> dict:
        return {
            "outcome": AnalysisGraphOutcome(
                application=state["application"],
                result="analyzed",
                match_score=state["document"].match_score,
            )
        }
