from dataclasses import dataclass
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from .ports import ApplicationAnalysisModel, ApplicationAnalysisStore
from .workspace import (
    ApplicationAnalysisDocument,
    ApplicationAnalysisDraft,
    ApplicationRecord,
)
from ...matching import EvidenceItem, EvidenceMatchingEngine, MatchingResult


AnalysisItemResult = Literal["analyzed", "repaired", "skipped"]


@dataclass(frozen=True)
class AnalysisGraphOutcome:
    application: ApplicationRecord
    result: AnalysisItemResult
    match_score: int | None
    errors: tuple[str, ...] = ()


class _AnalysisState(TypedDict, total=False):
    application_id: str
    application: ApplicationRecord
    draft: ApplicationAnalysisDraft
    evidence: tuple[EvidenceItem, ...]
    matching: MatchingResult
    document: ApplicationAnalysisDocument
    repair_score: int | None
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

    async def run(self, application_id: str) -> AnalysisGraphOutcome:
        state = await self._graph.ainvoke({"application_id": application_id})
        return state["outcome"]

    def _build_graph(self):
        graph = StateGraph(_AnalysisState)
        graph.add_node("load_and_revalidate_application", self._load_application)
        graph.add_node("inspect_existing_analysis", self._inspect_existing)
        graph.add_node("skip_ineligible", self._skip_ineligible)
        graph.add_node("repair_analysis_properties", self._repair_properties)
        graph.add_node("load_master_resume_evidence", self._load_evidence)
        graph.add_node("call_analysis_model", self._call_model)
        graph.add_node("match_skill_signals", self._match_signals)
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
        graph.add_edge("call_analysis_model", "match_skill_signals")
        graph.add_edge("match_skill_signals", "render_application_analysis")
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
        return {"draft": await self._model.analyze(state["application"])}

    async def _match_signals(self, state: _AnalysisState) -> dict:
        return {
            "matching": self._matcher.score(
                state["draft"].skill_signals, state["evidence"]
            )
        }

    async def _render_analysis(self, state: _AnalysisState) -> dict:
        return {
            "document": ApplicationAnalysisDocument(
                summary=" ".join(state["draft"].summary),
                match_score=state["matching"].score,
                skill_signals=state["draft"].skill_signals,
                heading="Application Analysis",
            )
        }

    async def _append_body(self, state: _AnalysisState) -> dict:
        await self._store.append_application_analysis(
            state["application"].id, state["document"]
        )
        return {}

    async def _commit_properties(self, state: _AnalysisState) -> dict:
        await self._store.finalize_application_analysis(
            state["application"].id,
            match_score=state["document"].match_score,
        )
        return {}

    async def _complete_analysis(self, state: _AnalysisState) -> dict:
        return {
            "outcome": AnalysisGraphOutcome(
                application=state["application"],
                result="analyzed",
                match_score=state["document"].match_score,
            )
        }
