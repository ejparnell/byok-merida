from merida_api.features.applications.workspace import (
    AnalysisModelResponse,
    ApplicationRecord,
)
from merida_api.features.resumes.workspace import (
    DocumentBlock,
    ResumeArtifactBundle,
    ResumeDocument,
)


class FakeApplicationAnalysisModel:
    async def generate(
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
            }
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
