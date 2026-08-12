import hashlib
import json

from merida_api.features.applications.analysis_authorization import (
    PreparedAnalysisCall,
)
from merida_api.features.applications.workspace import (
    AnalysisCallEvidence,
    AnalysisModelResponse,
    ApplicationRecord,
)
from merida_api.features.resumes.workspace import (
    DocumentBlock,
    ResumeArtifactBundle,
    ResumeDocument,
)


class FakeApplicationAnalysisModel:
    def prepare(
        self, application: ApplicationRecord, *, repair_code: str | None = None
    ) -> PreparedAnalysisCall:
        envelope = json.dumps(
            {
                "model": "deepseek-v4-flash",
                "messages": [
                    {"role": "system", "content": "Analyze job content."},
                    {
                        "role": "user",
                        "content": (
                            application.job_content or ""
                        )
                        + (f" Repair: {repair_code}" if repair_code else ""),
                    },
                ],
                "max_tokens": 8000,
                "response_format": {"type": "json_object"},
                "stream": False,
                "reasoning_effort": "high",
                "thinking": {"type": "enabled"},
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return PreparedAnalysisCall(
            endpoint="https://api.deepseek.com/v1/chat/completions",
            model="deepseek-v4-flash",
            max_output_tokens=8000,
            rendered_request=envelope,
            opaque=(application, repair_code),
        )

    async def transmit(
        self, prepared: PreparedAnalysisCall
    ) -> AnalysisModelResponse:
        application, repair_code = prepared.opaque
        return self._response(application, repair_code=repair_code)

    async def generate(
        self, application: ApplicationRecord, *, repair_code: str | None = None
    ) -> AnalysisModelResponse:
        return self._response(application, repair_code=repair_code)

    def _response(
        self, application: ApplicationRecord, *, repair_code: str | None = None
    ) -> AnalysisModelResponse:
        del repair_code
        vocabulary = {
            "React": ("react", "React"),
            "Python": ("python", "Python"),
            "REST APIs": ("rest api", "REST APIs"),
            "PostgreSQL": ("postgres", "PostgreSQL"),
            "Testing": ("test", "automated tests"),
            "CI": ("ci", "CI"),
            "Accessibility": ("accessib", "accessible"),
            "Observability": ("observab", "observability"),
        }
        content = (application.job_content or "").lower()
        signals = tuple(
            (name, evidence)
            for name, (token, evidence) in vocabulary.items()
            if token in content
        )
        signal_summary = (
            ", ".join(name for name, _evidence in signals)
            or "transferable engineering experience"
        )
        request_id = hashlib.sha256(
            f"{application.id}:{application.job_content}".encode()
        ).hexdigest()[:20]
        return AnalysisModelResponse(
            payload={
                "summary": [
                    f"{application.title} emphasizes {signal_summary}.",
                    "The analysis uses only readable Job Content and deterministic test evidence.",
                    "The durable Match Score is calculated outside the model.",
                ],
                "skillSignals": [
                    {
                        "name": name,
                        "category": "other",
                        "importance": "signal",
                        "evidence": evidence,
                    }
                    for name, evidence in signals
                ],
            },
            call_evidence=AnalysisCallEvidence(
                transmission_state="sent",
                finish_reason="stop",
                model_id="deepseek-v4-flash",
                request_id=f"fake-{request_id}",
                input_tokens=max(1, len(application.job_content or "") // 3),
                output_tokens=400,
                total_tokens=max(1, len(application.job_content or "") // 3)
                + 400,
                cache_hit_input_tokens=0,
                reasoning_output_tokens=200,
            ),
        )


class FakeResumeDocumentBuilder:
    async def build(
        self,
        application: ApplicationRecord,
        master_resume: ResumeDocument,
        **_context,
    ) -> ResumeArtifactBundle:
        signals = (
            tuple(signal.name for signal in application.analysis.skill_signals)
            if application.analysis
            else ()
        )
        score = application.match_score or 0
        return ResumeArtifactBundle(
            resume=(
                DocumentBlock(kind="heading_1", text="Elizabeth Parnell"),
                DocumentBlock(kind="heading_2", text=application.title),
                DocumentBlock(
                    kind="paragraph",
                    text="Evidence-backed application-ready test resume.",
                ),
                DocumentBlock(
                    kind="bulleted_list_item",
                    text=f"Relevant signals: {', '.join(signals) or 'transferable experience'}",
                ),
            ),
            note=(
                DocumentBlock(kind="heading_2", text="Resume Fit Analysis"),
                DocumentBlock(kind="paragraph", text=f"Match Score: {score}"),
                DocumentBlock(
                    kind="paragraph",
                    text=f"Compared against {master_resume.record.name} evidence.",
                ),
            ),
        )
