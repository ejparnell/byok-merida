from __future__ import annotations

from dataclasses import asdict
from datetime import date
import hashlib
import json

from ..applications.workspace import (
    ApplicationAnalysisDocument,
    ApplicationRecord,
    PersistedSkillSignal,
)
from .workspace import DocumentBlock, ResumeDocument, ResumeRecord


def canonical_document(value: dict) -> bytes:
    return json.dumps(
        value,
        default=lambda item: item.isoformat() if isinstance(item, date) else item,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def source_proof(value: dict) -> str:
    return hashlib.sha256(canonical_document(value)).hexdigest()


def master_document(value: ResumeDocument) -> dict:
    return json.loads(canonical_document(asdict(value)))


def restore_master(value: dict) -> ResumeDocument:
    record = value["record"]
    return ResumeDocument(
        record=ResumeRecord(
            id=record["id"],
            url=record["url"],
            name=record["name"],
            application_ids=tuple(record.get("application_ids", ())),
            archived=bool(record.get("archived", False)),
        ),
        blocks=tuple(DocumentBlock(**block) for block in value["blocks"]),
    )


def application_document(value: ApplicationRecord) -> dict:
    return json.loads(canonical_document(asdict(value)))


def restore_application(value: dict) -> ApplicationRecord:
    analysis = value.get("analysis")
    return ApplicationRecord(
        id=value["id"],
        url=value["url"],
        company_name=value["company_name"],
        role=value["role"],
        job_url=value["job_url"],
        captured_url=value.get("captured_url"),
        location=value.get("location"),
        date_found=date.fromisoformat(value["date_found"]),
        application_status=value["application_status"],
        analyzed=bool(value["analyzed"]),
        match_score=value.get("match_score"),
        resume_ids=tuple(value.get("resume_ids", ())),
        note_ids=tuple(value.get("note_ids", ())),
        job_content=value.get("job_content"),
        analysis=(
            ApplicationAnalysisDocument(
                summary=analysis["summary"],
                match_score=analysis.get("match_score"),
                skill_signals=tuple(
                    PersistedSkillSignal(**signal)
                    for signal in analysis.get("skill_signals", ())
                ),
                heading=analysis["heading"],
            )
            if analysis
            else None
        ),
    )
