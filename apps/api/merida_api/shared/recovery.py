from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Literal, Protocol


RecoveryWorkflow = Literal["capture", "resume_creation"]
RecoveryPhase = Literal[
    "intent",
    "application_created",
    "resume_created",
    "pdf_published",
    "note_created",
    "resolved",
]
CleanupStatus = Literal["not_required", "completed", "incomplete"]
RecoveryResolution = Literal[
    "active", "completed", "cleaned", "operator_acknowledged"
]
WORKFLOWS = {"capture", "resume_creation"}
PHASES = {
    "intent",
    "application_created",
    "resume_created",
    "pdf_published",
    "note_created",
    "resolved",
}
CLEANUP_STATUSES = {"not_required", "completed", "incomplete"}
RESOLUTIONS = {"active", "completed", "cleaned", "operator_acknowledged"}


class RecoveryJournalError(RuntimeError):
    pass


@dataclass(frozen=True)
class EffectEntry:
    run_id: str
    workflow: RecoveryWorkflow
    domain_key: str
    phase: RecoveryPhase
    started_at: str
    updated_at: str
    resume_id: str | None = None
    note_id: str | None = None
    pdf_id: str | None = None
    application_id: str | None = None
    cleanup_status: CleanupStatus = "not_required"
    cleanup_errors: tuple[str, ...] = ()
    resolution: RecoveryResolution = "active"


class EffectJournal(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def error(self) -> str | None: ...

    def start(
        self, *, workflow: RecoveryWorkflow, domain_key: str, run_id: str
    ) -> EffectEntry: ...
    def advance(
        self, run_id: str, *, phase: RecoveryPhase, **changes
    ) -> EffectEntry: ...
    def resolve(
        self,
        run_id: str,
        *,
        resolution: RecoveryResolution,
        cleanup_status: CleanupStatus = "not_required",
        cleanup_errors: tuple[str, ...] = (),
    ) -> EffectEntry: ...
    def unresolved(
        self, *, workflow: str | None = None, domain_key: str | None = None
    ) -> tuple[EffectEntry, ...]: ...
    def get(self, run_id: str) -> EffectEntry | None: ...
    def compact(self, *, max_age_days: int = 7) -> None: ...


class JsonEffectJournal:
    SCHEMA_VERSION = 1

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._entries = self._load()

    @property
    def available(self) -> bool:
        return True

    @property
    def error(self) -> str | None:
        return None

    def _load(self) -> dict[str, EffectEntry]:
        if not self._path.exists():
            return {}
        try:
            document = json.loads(self._path.read_text())
            if document.get("schemaVersion") != self.SCHEMA_VERSION:
                raise RecoveryJournalError("Recovery journal version is not supported.")
            entries = {}
            for item in document.get("entries", []):
                if (
                    item.get("workflow") not in WORKFLOWS
                    or item.get("phase") not in PHASES
                    or item.get("cleanup_status", "not_required")
                    not in CLEANUP_STATUSES
                    or item.get("resolution", "active") not in RESOLUTIONS
                ):
                    raise RecoveryJournalError(
                        "Recovery journal contains an invalid state."
                    )
                entry = EffectEntry(
                    **{
                        **item,
                        "cleanup_errors": tuple(item.get("cleanup_errors", ())),
                    }
                )
                entries[entry.run_id] = entry
            return entries
        except RecoveryJournalError:
            raise
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise RecoveryJournalError("Recovery journal could not be read.") from exc

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        document = {
            "schemaVersion": self.SCHEMA_VERSION,
            "entries": [asdict(entry) for entry in self._entries.values()],
        }
        temporary.write_text(json.dumps(document, indent=2) + "\n")
        temporary.replace(self._path)

    def start(
        self, *, workflow: RecoveryWorkflow, domain_key: str, run_id: str
    ) -> EffectEntry:
        now = datetime.now(timezone.utc).isoformat()
        entry = EffectEntry(
            run_id=run_id,
            workflow=workflow,
            domain_key=domain_key,
            phase="intent",
            started_at=now,
            updated_at=now,
        )
        with self._lock:
            self._entries[run_id] = entry
            self._save()
        return entry

    def advance(
        self, run_id: str, *, phase: RecoveryPhase, **changes
    ) -> EffectEntry:
        with self._lock:
            current = self._entries[run_id]
            entry = replace(
                current,
                phase=phase,
                updated_at=datetime.now(timezone.utc).isoformat(),
                **changes,
            )
            self._entries[run_id] = entry
            self._save()
        return entry

    def resolve(
        self,
        run_id: str,
        *,
        resolution: RecoveryResolution,
        cleanup_status: CleanupStatus = "not_required",
        cleanup_errors: tuple[str, ...] = (),
    ) -> EffectEntry:
        return self.advance(
            run_id,
            phase="resolved",
            resolution=resolution,
            cleanup_status=cleanup_status,
            cleanup_errors=cleanup_errors,
        )

    def unresolved(
        self, *, workflow: str | None = None, domain_key: str | None = None
    ) -> tuple[EffectEntry, ...]:
        with self._lock:
            return tuple(
                entry
                for entry in self._entries.values()
                if entry.resolution == "active"
                and (workflow is None or entry.workflow == workflow)
                and (domain_key is None or entry.domain_key == domain_key)
            )

    def get(self, run_id: str) -> EffectEntry | None:
        with self._lock:
            return self._entries.get(run_id)

    def compact(self, *, max_age_days: int = 7) -> None:
        cutoff = datetime.now(timezone.utc).timestamp() - max_age_days * 86400
        with self._lock:
            compacted = {
                run_id: entry
                for run_id, entry in self._entries.items()
                if entry.resolution == "active"
                or datetime.fromisoformat(entry.updated_at).timestamp() >= cutoff
            }
            if len(compacted) != len(self._entries):
                self._entries = compacted
                self._save()


class UnavailableEffectJournal:
    def __init__(self, error: str):
        self._error = error

    @property
    def available(self) -> bool:
        return False

    @property
    def error(self) -> str:
        return self._error

    def start(self, **_kwargs):
        raise RecoveryJournalError(self._error)

    def advance(self, *_args, **_kwargs):
        raise RecoveryJournalError(self._error)

    def resolve(self, *_args, **_kwargs):
        raise RecoveryJournalError(self._error)

    def unresolved(self, **_kwargs) -> tuple[EffectEntry, ...]:
        return ()

    def get(self, _run_id: str) -> EffectEntry | None:
        return None

    def compact(self, *, max_age_days: int = 7) -> None:
        del max_age_days
