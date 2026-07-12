from merida_api.features.applications.workspace import (
    ApplicationAnalysisDocument,
    ApplicationRecord,
)
from merida_api.features.resumes.workspace import (
    DocumentBlock,
    ResumeArtifactBundle,
    ResumeDocument,
)


class FakeApplicationAnalysisModel:
    async def analyze(
        self, application: ApplicationRecord
    ) -> ApplicationAnalysisDocument:
        vocabulary = {
            "React": "react",
            "Python": "python",
            "REST APIs": "rest api",
            "PostgreSQL": "postgres",
            "Testing": "test",
            "CI": "ci",
            "Accessibility": "accessib",
            "Observability": "observab",
        }
        content = (application.job_content or "").lower()
        signals = tuple(
            name for name, token in vocabulary.items() if token in content
        )
        score = min(96, 58 + len(signals) * 6)
        signal_summary = ", ".join(signals) or "transferable engineering experience"
        return ApplicationAnalysisDocument(
            summary=(
                f"{application.title} emphasizes {signal_summary}. "
                "The analysis uses only readable Job Content and deterministic test evidence. "
                "Review the durable record in Notion before applying."
            ),
            match_score=score,
            skill_signals=signals,
            heading="Application Analysis",
        )


class FakeResumeDocumentBuilder:
    async def build(
        self, application: ApplicationRecord, master_resume: ResumeDocument
    ) -> ResumeArtifactBundle:
        signals = application.analysis.skill_signals if application.analysis else ()
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
            pdf_lines=(
                "Elizabeth Parnell",
                application.title,
                "Evidence-backed application-ready test resume",
                f"Match Score: {score}",
                "Skills: " + ", ".join(signals),
            ),
        )
