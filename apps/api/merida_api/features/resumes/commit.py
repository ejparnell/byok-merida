from dataclasses import dataclass
from pathlib import Path

from .ports import ResumeCreationStore, ResumePdfArtifacts
from .workspace import NoteRecord, ResumeArtifactBundle, ResumeRecord
from ..applications.workspace import ApplicationRecord
from ...shared.recovery import EffectEntry, EffectJournal


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
        self,
        store: ResumeCreationStore,
        pdfs: ResumePdfArtifacts,
        journal: EffectJournal | None = None,
    ):
        self._store = store
        self._pdfs = pdfs
        self._journal = journal

    async def commit(
        self,
        application: ApplicationRecord,
        bundle: ResumeArtifactBundle,
        *,
        run_id: str | None = None,
        staged_pdf: Path | None = None,
    ) -> ArtifactCommitResult:
        resume: ResumeRecord | None = None
        note: NoteRecord | None = None
        pdf_path: Path | None = None
        resume_create_attempted = False
        note_create_attempted = False
        attachment_attempted = False
        staged = staged_pdf or self.stage(bundle)
        try:
            if self._journal is not None and run_id is not None:
                self._journal.start(
                    workflow="resume_creation",
                    domain_key=application.id,
                    run_id=run_id,
                )

            def resume_created(created: ResumeRecord) -> None:
                nonlocal resume
                resume = created
                self._advance(
                    run_id,
                    phase="resume_created",
                    resume_id=created.id,
                    application_id=application.id,
                )

            resume_create_attempted = True
            resume = await self._store.create_resume_draft(
                application.title,
                bundle.resume,
                on_created=resume_created,
            )
            pdf_path = self._pdfs.publish(resume.id, staged)
            self._advance(run_id, phase="pdf_published", pdf_id=resume.id)
            def note_created(created: NoteRecord) -> None:
                nonlocal note
                note = created
                self._advance(run_id, phase="note_created", note_id=created.id)

            note_create_attempted = True
            note = await self._store.create_resume_fit_note(
                f"Resume Fit Analysis - {application.title}",
                application_id=application.id,
                resume_id=resume.id,
                document=bundle.note,
                on_created=note_created,
            )
            attachment_attempted = True
            resume = await self._store.attach_resume_to_application(
                resume.id, application.id
            )
            if self._journal is not None and run_id is not None:
                self._journal.resolve(run_id, resolution="completed")
            return ArtifactCommitResult(
                resume=resume,
                note=note,
                pdf_path=pdf_path,
                cleanup_status="not_required",
            )
        except Exception:
            self._pdfs.discard(staged)
            cleanup_errors = await self._cleanup(
                resume_id=resume.id if resume else None,
                note_id=note.id if note else None,
                pdf_id=resume.id if pdf_path is not None and resume else None,
                clear_relation=attachment_attempted,
            )
            cleanup_errors = list(cleanup_errors)
            if resume_create_attempted and resume is None:
                cleanup_errors.append(
                    "Resume draft ownership could not be confirmed; manual recovery is required."
                )
            if note_create_attempted and note is None:
                cleanup_errors.append(
                    "Resume Fit Analysis Note ownership could not be confirmed; manual recovery is required."
                )
            if self._journal is not None and run_id is not None:
                self._journal.resolve(
                    run_id,
                    resolution="cleaned" if not cleanup_errors else "active",
                    cleanup_status="completed" if not cleanup_errors else "incomplete",
                    cleanup_errors=tuple(cleanup_errors),
                )
            return ArtifactCommitResult(
                resume=None,
                note=None,
                pdf_path=None,
                cleanup_status="incomplete" if cleanup_errors else "completed",
                cleanup_errors=tuple(cleanup_errors),
            )

    def stage(self, bundle: ResumeArtifactBundle) -> Path:
        return self._pdfs.stage(bundle.resume_document)

    def _advance(self, run_id: str | None, *, phase: str, **changes) -> None:
        if self._journal is not None and run_id is not None:
            self._journal.advance(run_id, phase=phase, **changes)

    async def reconcile(self, entry: EffectEntry) -> tuple[str, tuple[str, ...]]:
        if not any((entry.resume_id, entry.note_id, entry.pdf_id)):
            return (
                "incomplete",
                ("Artifact ownership could not be reconstructed safely.",),
            )
        verified = await self._store.verify_recovery_artifacts(
            application_id=entry.domain_key,
            resume_id=entry.resume_id,
            note_id=entry.note_id,
        )
        if not verified:
            return (
                "incomplete",
                ("Recorded artifacts could not be verified for safe cleanup.",),
            )
        errors = await self._cleanup(
            resume_id=entry.resume_id,
            note_id=entry.note_id,
            pdf_id=entry.pdf_id,
            clear_relation=True,
        )
        return ("incomplete" if errors else "completed", errors)

    async def _cleanup(
        self,
        *,
        resume_id: str | None,
        note_id: str | None,
        pdf_id: str | None,
        clear_relation: bool,
    ) -> tuple[str, ...]:
        errors = []
        if clear_relation and resume_id:
            try:
                await self._store.clear_resume_application(resume_id)
            except Exception:
                errors.append(
                    "Partial Resume-to-Application relation could not be cleared."
                )
        if note_id:
            try:
                await self._store.archive_note(note_id)
            except Exception:
                errors.append("Resume Fit Analysis Note could not be archived.")
        if pdf_id:
            try:
                self._pdfs.remove(pdf_id)
            except Exception:
                errors.append("Generated PDF could not be removed.")
        if resume_id:
            try:
                await self._store.archive_resume(resume_id)
            except Exception:
                errors.append("Resume draft could not be archived.")
        return tuple(errors)

    def pdf_path(self, resume_id: str) -> Path | None:
        return self._pdfs.path(resume_id)
