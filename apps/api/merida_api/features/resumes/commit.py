from dataclasses import dataclass
from pathlib import Path

from .ports import ResumeCreationStore, ResumePdfArtifacts
from .workspace import NoteRecord, ResumeArtifactBundle, ResumeRecord
from ..applications.workspace import ApplicationRecord


@dataclass(frozen=True)
class ArtifactCommitResult:
    resume: ResumeRecord | None
    note: NoteRecord | None
    pdf_path: Path | None
    cleanup_status: str
    cleanup_errors: tuple[str, ...] = ()

    @property
    def committed(self) -> bool:
        return (
            self.resume is not None
            and self.note is not None
            and self.pdf_path is not None
            and self.cleanup_status == "not_required"
        )


class ResumeArtifactCommitter:
    def __init__(
        self, store: ResumeCreationStore, pdfs: ResumePdfArtifacts
    ):
        self._store = store
        self._pdfs = pdfs

    async def commit(
        self, application: ApplicationRecord, bundle: ResumeArtifactBundle
    ) -> ArtifactCommitResult:
        resume: ResumeRecord | None = None
        note: NoteRecord | None = None
        pdf_path: Path | None = None
        attachment_attempted = False
        try:
            resume = await self._store.create_resume_draft(
                application.title, bundle.resume
            )
            pdf_path = self._pdfs.save(resume.id, bundle.pdf_lines)
            note = await self._store.create_resume_fit_note(
                f"Resume Fit Analysis - {application.title}",
                application_id=application.id,
                resume_id=resume.id,
                document=bundle.note,
            )
            attachment_attempted = True
            resume = await self._store.attach_resume_to_application(
                resume.id, application.id
            )
            return ArtifactCommitResult(
                resume=resume,
                note=note,
                pdf_path=pdf_path,
                cleanup_status="not_required",
            )
        except Exception:
            cleanup_errors = []
            if attachment_attempted and resume is not None:
                try:
                    await self._store.clear_resume_application(resume.id)
                except Exception:
                    cleanup_errors.append(
                        "Partial Resume-to-Application relation could not be cleared."
                    )
            if note is not None:
                try:
                    await self._store.archive_note(note.id)
                except Exception:
                    cleanup_errors.append(
                        "Resume Fit Analysis Note could not be archived."
                    )
            if pdf_path is not None and resume is not None:
                try:
                    self._pdfs.remove(resume.id)
                except Exception:
                    cleanup_errors.append("Generated PDF could not be removed.")
            if resume is not None:
                try:
                    await self._store.archive_resume(resume.id)
                except Exception:
                    cleanup_errors.append("Resume draft could not be archived.")
            return ArtifactCommitResult(
                resume=None,
                note=None,
                pdf_path=None,
                cleanup_status="incomplete" if cleanup_errors else "completed",
                cleanup_errors=tuple(cleanup_errors),
            )

    def pdf_path(self, resume_id: str) -> Path | None:
        return self._pdfs.path(resume_id)
