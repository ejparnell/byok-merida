from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Iterator

from .checkpoint_vault import EncryptedCheckpoint


RESUME_SPEND_CEILING_MICROS = 1_000_000


class ResumeRunStoreError(RuntimeError):
    pass


class ActiveResumeRunError(ResumeRunStoreError):
    def __init__(self, active_run_id: str):
        super().__init__("A Resume Run is already active.")
        self.active_run_id = active_run_id


class ResumeRunIdempotencyConflictError(ResumeRunStoreError):
    pass


class ResumeSpendLimitReached(ResumeRunStoreError):
    pass


class ResumeRunStopping(ResumeRunStoreError):
    pass


class ResumeArtifactStateChanged(ResumeRunStoreError):
    pass


class ResumeArtifactActionUnavailable(ResumeRunStoreError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteResumeRunStore:
    """Content-free Resume Run coordination and spend authority."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = RLock()
        self.available = True
        self.transactional = True
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize()
        except (OSError, sqlite3.Error):
            self.available = False
            self.transactional = False

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        if not self.available:
            raise ResumeRunStoreError("Resume Run store is unavailable.")
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS resume_runs (
                  run_id TEXT PRIMARY KEY,
                  creation_order INTEGER NOT NULL UNIQUE,
                  idempotency_key TEXT NOT NULL UNIQUE,
                  target INTEGER NOT NULL CHECK(target BETWEEN 1 AND 10),
                  lifecycle TEXT NOT NULL,
                  outcome TEXT,
                  reason_code TEXT,
                  revision INTEGER NOT NULL CHECK(revision >= 1),
                  created_at TEXT NOT NULL,
                  started_at TEXT,
                  stopping_decided_at TEXT,
                  finished_at TEXT,
                  updated_at TEXT NOT NULL,
                  spend_ceiling_micros INTEGER NOT NULL CHECK(spend_ceiling_micros = 1000000),
                  verified_cost_micros INTEGER NOT NULL DEFAULT 0 CHECK(verified_cost_micros >= 0),
                  active_reservation_micros INTEGER NOT NULL DEFAULT 0 CHECK(active_reservation_micros >= 0),
                  indeterminate_reservation_micros INTEGER NOT NULL DEFAULT 0 CHECK(indeterminate_reservation_micros >= 0),
                  queue_exhausted INTEGER NOT NULL DEFAULT 0 CHECK(queue_exhausted IN (0,1))
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_resume_run
                  ON resume_runs((1)) WHERE lifecycle != 'finished';
                CREATE TABLE IF NOT EXISTS resume_candidates (
                  run_id TEXT NOT NULL REFERENCES resume_runs(run_id),
                  ordinal INTEGER NOT NULL,
                  application_id TEXT NOT NULL,
                  application_label TEXT NOT NULL,
                  state TEXT NOT NULL DEFAULT 'pending',
                  stage TEXT,
                  reason_code TEXT,
                  evaluation_consumed INTEGER NOT NULL DEFAULT 0,
                  artifact_set_id TEXT,
                  completion_json TEXT,
                  considered_at TEXT,
                  updated_at TEXT NOT NULL,
                  terminal_at TEXT,
                  PRIMARY KEY(run_id, ordinal),
                  UNIQUE(run_id, application_id)
                );
                CREATE TABLE IF NOT EXISTS resume_calls (
                  call_id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL REFERENCES resume_runs(run_id),
                  application_id TEXT NOT NULL,
                  stage TEXT NOT NULL,
                  attempt INTEGER NOT NULL CHECK(attempt BETWEEN 1 AND 2),
                  state TEXT NOT NULL,
                  reservation_micros INTEGER NOT NULL CHECK(reservation_micros >= 0),
                  verified_cost_micros INTEGER,
                  approval_fingerprint TEXT NOT NULL,
                  request_fingerprint TEXT NOT NULL,
                  authorization_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE(run_id, application_id, stage, attempt)
                );
                CREATE TABLE IF NOT EXISTS resume_artifact_sets (
                  artifact_set_id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL REFERENCES resume_runs(run_id),
                  application_id TEXT NOT NULL,
                  candidate_ordinal INTEGER NOT NULL,
                  application_label TEXT NOT NULL,
                  revision INTEGER NOT NULL,
                  disposition TEXT NOT NULL,
                  pending_boundary TEXT,
                  quarantine_json TEXT,
                  active_action_json TEXT,
                  completion_json TEXT,
                  pdf_path TEXT,
                  pdf_digest TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS resume_action_bindings (
                  idempotency_key TEXT PRIMARY KEY,
                  artifact_set_id TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  expected_revision INTEGER NOT NULL,
                  accepted_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS resume_checkpoints (
                  checkpoint_id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL REFERENCES resume_runs(run_id),
                  candidate_ordinal INTEGER,
                  kind TEXT NOT NULL,
                  schema_version INTEGER NOT NULL,
                  source_proof TEXT NOT NULL,
                  producing_call_id TEXT,
                  artifact_set_id TEXT,
                  key_version TEXT NOT NULL,
                  nonce BLOB NOT NULL,
                  ciphertext BLOB NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  UNIQUE(run_id,kind,candidate_ordinal)
                );
                """
            )

    def start(
        self,
        *,
        run_id: str,
        idempotency_key: str,
        target: int,
        candidates: list[tuple[str, str]],
        queue_exhausted: bool,
        master_source_proof: str | None = None,
        master_checkpoint: EncryptedCheckpoint | None = None,
    ) -> dict:
        with self._write() as connection:
            existing = connection.execute(
                "SELECT run_id, target FROM resume_runs WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                if existing["target"] != target:
                    raise ResumeRunIdempotencyConflictError
                return self._snapshot(connection, existing["run_id"])
            active = connection.execute(
                "SELECT run_id FROM resume_runs WHERE lifecycle != 'finished'"
            ).fetchone()
            if active:
                raise ActiveResumeRunError(active["run_id"])
            timestamp = _now()
            order = connection.execute(
                "SELECT COALESCE(MAX(creation_order),0)+1 FROM resume_runs"
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO resume_runs
                (run_id,creation_order,idempotency_key,target,lifecycle,revision,
                 created_at,updated_at,spend_ceiling_micros,queue_exhausted)
                VALUES(?,?,?,?, 'queued',1,?,?,?,?)""",
                (
                    run_id,
                    order,
                    idempotency_key,
                    target,
                    timestamp,
                    timestamp,
                    RESUME_SPEND_CEILING_MICROS,
                    int(queue_exhausted),
                ),
            )
            connection.executemany(
                """INSERT INTO resume_candidates
                (run_id,ordinal,application_id,application_label,updated_at)
                VALUES(?,?,?,?,?)""",
                [
                    (run_id, ordinal, application_id, label, timestamp)
                    for ordinal, (application_id, label) in enumerate(candidates)
                ],
            )
            if master_source_proof is not None and master_checkpoint is not None:
                connection.execute(
                    """INSERT INTO resume_checkpoints VALUES(
                    ?,?,NULL,'master_source',1,?,NULL,NULL,?,?,?,?,?)""",
                    (
                        f"master:{run_id}", run_id, master_source_proof,
                        master_checkpoint.key_version, master_checkpoint.nonce,
                        master_checkpoint.ciphertext, timestamp, timestamp,
                    ),
                )
            return self._snapshot(connection, run_id)

    def replay(self, idempotency_key: str, target: int) -> dict | None:
        if not self.available:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT run_id,target FROM resume_runs WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if row is None:
                return None
            if row["target"] != target:
                raise ResumeRunIdempotencyConflictError
            return self._snapshot(connection, row["run_id"])

    def get(self, run_id: str) -> dict | None:
        if not self.available:
            return None
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM resume_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            return self._snapshot(connection, run_id) if exists else None

    def active(self) -> dict | None:
        if not self.available:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT run_id FROM resume_runs WHERE lifecycle != 'finished'"
            ).fetchone()
            return self._snapshot(connection, row["run_id"]) if row else None

    def latest(self) -> dict | None:
        if not self.available:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT run_id FROM resume_runs ORDER BY creation_order DESC LIMIT 1"
            ).fetchone()
            return self._snapshot(connection, row["run_id"]) if row else None

    def begin(self, run_id: str) -> dict:
        with self._write() as connection:
            now = _now()
            connection.execute(
                """UPDATE resume_runs SET lifecycle='running',started_at=COALESCE(started_at,?),
                updated_at=?,revision=revision+1 WHERE run_id=? AND lifecycle='queued'""",
                (now, now, run_id),
            )
            return self._snapshot(connection, run_id)

    def begin_candidate(self, run_id: str, ordinal: int) -> bool:
        with self._write() as connection:
            run = connection.execute(
                "SELECT lifecycle,outcome FROM resume_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if not run or run["lifecycle"] != "running" or run["outcome"] is not None:
                return False
            now = _now()
            changed = connection.execute(
                """UPDATE resume_candidates SET state='evaluating',stage='admission',
                evaluation_consumed=1,considered_at=COALESCE(considered_at,?),updated_at=?
                WHERE run_id=? AND ordinal=? AND state='pending'""",
                (now, now, run_id, ordinal),
            ).rowcount
            if changed:
                connection.execute(
                    "UPDATE resume_runs SET revision=revision+1,updated_at=? WHERE run_id=?",
                    (now, run_id),
                )
            return bool(changed)

    def admit_candidate(
        self,
        run_id: str,
        ordinal: int,
        *,
        source_proof: str,
        checkpoint: EncryptedCheckpoint,
    ) -> bool:
        with self._write() as connection:
            run = connection.execute(
                "SELECT lifecycle,outcome FROM resume_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if not run or run["lifecycle"] != "running" or run["outcome"] is not None:
                return False
            now = _now()
            changed = connection.execute(
                """UPDATE resume_candidates SET state='evaluating',stage='admission',
                evaluation_consumed=1,considered_at=COALESCE(considered_at,?),updated_at=?
                WHERE run_id=? AND ordinal=? AND state='pending'""",
                (now, now, run_id, ordinal),
            ).rowcount
            if changed != 1:
                return False
            connection.execute(
                """INSERT INTO resume_checkpoints VALUES(
                ?,?,?,'candidate_source',1,?,NULL,NULL,?,?,?,?,?)""",
                (
                    f"candidate:{run_id}:{ordinal}", run_id, ordinal, source_proof,
                    checkpoint.key_version, checkpoint.nonce, checkpoint.ciphertext,
                    now, now,
                ),
            )
            connection.execute(
                "UPDATE resume_runs SET revision=revision+1,updated_at=? WHERE run_id=?",
                (now, run_id),
            )
            return True

    def checkpoint(
        self, run_id: str, kind: str, candidate_ordinal: int | None = None
    ) -> tuple[str, EncryptedCheckpoint] | None:
        with self._connect() as connection:
            if candidate_ordinal is None:
                row = connection.execute(
                    """SELECT source_proof,key_version,nonce,ciphertext
                    FROM resume_checkpoints WHERE run_id=? AND kind=?
                    AND candidate_ordinal IS NULL""",
                    (run_id, kind),
                ).fetchone()
            else:
                row = connection.execute(
                    """SELECT source_proof,key_version,nonce,ciphertext
                    FROM resume_checkpoints WHERE run_id=? AND kind=?
                    AND candidate_ordinal=?""",
                    (run_id, kind, candidate_ordinal),
                ).fetchone()
            if row is None:
                return None
            return row["source_proof"], EncryptedCheckpoint(
                row["key_version"], bytes(row["nonce"]), bytes(row["ciphertext"])
            )

    def complete_candidate(
        self,
        run_id: str,
        ordinal: int,
        *,
        artifact_set_id: str,
        completion: dict,
        pdf_path: str | None,
        pdf_digest: str | None,
    ) -> dict:
        with self._write() as connection:
            now = _now()
            encoded = json.dumps(completion, separators=(",", ":"), sort_keys=True)
            connection.execute(
                """UPDATE resume_candidates SET state='completed',stage='completion_gate',
                artifact_set_id=?,completion_json=?,reason_code=NULL,updated_at=?,terminal_at=?
                WHERE run_id=? AND ordinal=?""",
                (artifact_set_id, encoded, now, now, run_id, ordinal),
            )
            candidate = connection.execute(
                "SELECT application_id,application_label FROM resume_candidates WHERE run_id=? AND ordinal=?",
                (run_id, ordinal),
            ).fetchone()
            changed = connection.execute(
                """UPDATE resume_artifact_sets SET disposition='sealed',pending_boundary=NULL,
                completion_json=?,pdf_path=?,pdf_digest=?,revision=revision+1,updated_at=?
                WHERE artifact_set_id=? AND run_id=? AND candidate_ordinal=?""",
                (encoded, pdf_path, pdf_digest, now, artifact_set_id, run_id, ordinal),
            ).rowcount
            if changed != 1:
                raise ResumeRunStoreError("The Resume Artifact Set intent is unavailable.")
            connection.execute(
                "DELETE FROM resume_checkpoints WHERE artifact_set_id=? AND kind='artifact'",
                (artifact_set_id,),
            )
            count = connection.execute(
                "SELECT COUNT(*) FROM resume_candidates WHERE run_id=? AND state='completed'",
                (run_id,),
            ).fetchone()[0]
            run = connection.execute(
                "SELECT target,outcome FROM resume_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if count >= run["target"] and run["outcome"] is None:
                connection.execute(
                    """UPDATE resume_runs SET outcome='target_met',reason_code='target_met',
                    stopping_decided_at=?,revision=revision+1,updated_at=? WHERE run_id=?""",
                    (now, now, run_id),
                )
            else:
                connection.execute(
                    "UPDATE resume_runs SET revision=revision+1,updated_at=? WHERE run_id=?",
                    (now, run_id),
                )
            return self._snapshot(connection, run_id)

    def start_artifact_set(
        self,
        *,
        artifact_set_id: str,
        run_id: str,
        ordinal: int,
        checkpoint_source_proof: str,
        checkpoint: EncryptedCheckpoint,
    ) -> None:
        with self._write() as connection:
            candidate = connection.execute(
                """SELECT application_id,application_label,state FROM resume_candidates
                WHERE run_id=? AND ordinal=?""",
                (run_id, ordinal),
            ).fetchone()
            run = connection.execute(
                "SELECT lifecycle,outcome FROM resume_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if (
                candidate is None or candidate["state"] != "evaluating"
                or run is None or run["lifecycle"] != "running" or run["outcome"] is not None
            ):
                raise ResumeRunStopping("The Resume Run cannot begin artifact work.")
            now = _now()
            connection.execute(
                """INSERT INTO resume_artifact_sets
                (artifact_set_id,run_id,application_id,candidate_ordinal,application_label,
                 revision,disposition,pending_boundary,created_at,updated_at)
                VALUES(?,?,?,?,?,1,'recoverable','pdf_staging',?,?)""",
                (
                    artifact_set_id, run_id, candidate["application_id"], ordinal,
                    candidate["application_label"], now, now,
                ),
            )
            connection.execute(
                """INSERT INTO resume_checkpoints VALUES(
                ?,?,?,'artifact',1,?,NULL,?, ?,?,?,?,?)""",
                (
                    f"artifact:{artifact_set_id}", run_id, ordinal,
                    checkpoint_source_proof, artifact_set_id, checkpoint.key_version,
                    checkpoint.nonce, checkpoint.ciphertext, now, now,
                ),
            )
            connection.execute(
                """UPDATE resume_candidates SET artifact_set_id=?,stage='artifact_recovery',updated_at=?
                WHERE run_id=? AND ordinal=?""",
                (artifact_set_id, now, run_id, ordinal),
            )
            connection.execute(
                "UPDATE resume_runs SET revision=revision+1,updated_at=? WHERE run_id=?",
                (now, run_id),
            )

    def fail_candidate(self, run_id: str, ordinal: int, reason: str) -> None:
        with self._write() as connection:
            now = _now()
            connection.execute(
                """UPDATE resume_candidates SET state='failed',reason_code=?,updated_at=?,terminal_at=?
                WHERE run_id=? AND ordinal=?""",
                (reason, now, now, run_id, ordinal),
            )
            connection.execute(
                "UPDATE resume_runs SET revision=revision+1,updated_at=? WHERE run_id=?",
                (now, run_id),
            )

    def finish(self, run_id: str) -> dict:
        with self._write() as connection:
            run = connection.execute(
                "SELECT outcome,queue_exhausted FROM resume_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if run is None:
                raise ResumeRunStoreError("Resume Run not found.")
            now = _now()
            outcome = run["outcome"] or (
                "queue_exhausted" if run["queue_exhausted"] else "attempt_budget_exhausted"
            )
            reason = run["outcome"] and connection.execute(
                "SELECT reason_code FROM resume_runs WHERE run_id=?", (run_id,)
            ).fetchone()[0] or outcome
            connection.execute(
                """UPDATE resume_runs SET lifecycle='finished',outcome=?,reason_code=?,
                stopping_decided_at=COALESCE(stopping_decided_at,?),finished_at=?,updated_at=?,revision=revision+1
                WHERE run_id=?""",
                (outcome, reason, now, now, now, run_id),
            )
            return self._snapshot(connection, run_id)

    def cancel(self, run_id: str) -> dict | None:
        with self._write() as connection:
            run = connection.execute(
                "SELECT lifecycle,outcome FROM resume_runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if run is None:
                return None
            if run["lifecycle"] == "finished":
                return self._snapshot(connection, run_id)
            now = _now()
            connection.execute(
                """UPDATE resume_runs SET lifecycle='cancelling',outcome=COALESCE(outcome,'cancelled'),
                reason_code=COALESCE(reason_code,'operator_cancelled'),
                stopping_decided_at=COALESCE(stopping_decided_at,?),updated_at=?,revision=revision+1
                WHERE run_id=?""",
                (now, now, run_id),
            )
            return self._snapshot(connection, run_id)

    def finish_cancellation(self, run_id: str) -> dict:
        with self._write() as connection:
            now = _now()
            connection.execute(
                """UPDATE resume_candidates SET state='cancelled',reason_code='operator_cancelled',
                considered_at=COALESCE(considered_at,?),updated_at=?,terminal_at=?
                WHERE run_id=? AND state IN ('pending','evaluating','recovering')""",
                (now, now, now, run_id),
            )
            connection.execute(
                """UPDATE resume_runs SET lifecycle='finished',outcome='cancelled',
                reason_code=COALESCE(reason_code,'operator_cancelled'),
                stopping_decided_at=COALESCE(stopping_decided_at,?),finished_at=?,updated_at=?,revision=revision+1
                WHERE run_id=? AND lifecycle='cancelling'""",
                (now, now, now, run_id),
            )
            return self._snapshot(connection, run_id)

    def reserve_call(
        self,
        *,
        call_id: str,
        run_id: str,
        application_id: str,
        stage: str,
        attempt: int,
        reservation_micros: int,
        approval_fingerprint: str,
        request_fingerprint: str,
        authorization: dict,
    ) -> None:
        with self._write() as connection:
            run = connection.execute(
                """SELECT lifecycle,outcome,spend_ceiling_micros,verified_cost_micros,
                active_reservation_micros,indeterminate_reservation_micros
                FROM resume_runs WHERE run_id=?""",
                (run_id,),
            ).fetchone()
            if run is None or run["lifecycle"] != "running" or run["outcome"] is not None:
                raise ResumeRunStopping("The Resume Run is stopping.")
            committed = sum(run[key] for key in (
                "verified_cost_micros", "active_reservation_micros", "indeterminate_reservation_micros"
            ))
            if committed + reservation_micros > run["spend_ceiling_micros"]:
                raise ResumeSpendLimitReached
            now = _now()
            connection.execute(
                """INSERT INTO resume_calls VALUES(?,?,?,?,?,'reserved',?,NULL,?,?,?,?,?)""",
                (
                    call_id, run_id, application_id, stage, attempt,
                    reservation_micros, approval_fingerprint, request_fingerprint,
                    json.dumps(authorization, separators=(",", ":"), sort_keys=True), now, now,
                ),
            )
            connection.execute(
                """UPDATE resume_runs SET active_reservation_micros=active_reservation_micros+?,
                revision=revision+1,updated_at=? WHERE run_id=?""",
                (reservation_micros, now, run_id),
            )

    def next_call_attempt(self, run_id: str, application_id: str, stage: str) -> int:
        with self._connect() as connection:
            count = connection.execute(
                """SELECT COUNT(*) FROM resume_calls
                WHERE run_id=? AND application_id=? AND stage=?""",
                (run_id, application_id, stage),
            ).fetchone()[0]
        attempt = count + 1
        if attempt > 2:
            raise ResumeRunStoreError("The Resume stage dispatch budget is exhausted.")
        return attempt

    def mark_call_dispatching(self, call_id: str) -> None:
        with self._write() as connection:
            now = _now()
            changed = connection.execute(
                """UPDATE resume_calls SET state='dispatching',updated_at=?
                WHERE call_id=? AND state='reserved'""",
                (now, call_id),
            ).rowcount
            if changed != 1:
                raise ResumeRunStoreError("The Resume Call Reservation is unavailable.")

    def resolve_call(
        self,
        call_id: str,
        *,
        transmission_state: str,
        verified_cost_micros: int | None,
    ) -> None:
        with self._write() as connection:
            call = connection.execute(
                """SELECT run_id,state,reservation_micros FROM resume_calls
                WHERE call_id=?""",
                (call_id,),
            ).fetchone()
            if call is None or call["state"] not in {"reserved", "dispatching"}:
                return
            now = _now()
            reservation = call["reservation_micros"]
            if verified_cost_micros is not None:
                if not 0 <= verified_cost_micros <= reservation:
                    raise ResumeRunStoreError("Verified cost exceeds its authorization.")
                state = "settled"
                active_delta = -reservation
                verified_delta = verified_cost_micros
                indeterminate_delta = 0
            elif transmission_state == "not_transmitted":
                state = "not_transmitted"
                active_delta = -reservation
                verified_delta = 0
                indeterminate_delta = 0
            else:
                state = "indeterminate"
                active_delta = -reservation
                verified_delta = 0
                indeterminate_delta = reservation
            connection.execute(
                """UPDATE resume_calls SET state=?,verified_cost_micros=?,updated_at=?
                WHERE call_id=?""",
                (state, verified_cost_micros, now, call_id),
            )
            connection.execute(
                """UPDATE resume_runs SET
                active_reservation_micros=active_reservation_micros+?,
                verified_cost_micros=verified_cost_micros+?,
                indeterminate_reservation_micros=indeterminate_reservation_micros+?,
                revision=revision+1,updated_at=? WHERE run_id=?""",
                (
                    active_delta,
                    verified_delta,
                    indeterminate_delta,
                    now,
                    call["run_id"],
                ),
            )

    def artifact_set(self, artifact_set_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM resume_artifact_sets WHERE artifact_set_id=?", (artifact_set_id,)
            ).fetchone()
            return self._artifact_snapshot(row) if row else None

    def request_artifact_action(
        self,
        *,
        artifact_set_id: str,
        kind: str,
        expected_revision: int,
        idempotency_key: str,
    ) -> dict | None:
        with self._write() as connection:
            existing = connection.execute(
                "SELECT artifact_set_id,kind,expected_revision FROM resume_action_bindings WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if existing and (
                existing["artifact_set_id"] != artifact_set_id
                or existing["kind"] != kind
                or existing["expected_revision"] != expected_revision
            ):
                raise ResumeArtifactStateChanged
            row = connection.execute(
                "SELECT * FROM resume_artifact_sets WHERE artifact_set_id=?",
                (artifact_set_id,),
            ).fetchone()
            if row is None:
                return None
            if existing:
                return self._artifact_snapshot(row)
            if row["revision"] != expected_revision:
                raise ResumeArtifactStateChanged
            available = self._artifact_snapshot(row)["availableActions"]
            if kind not in available:
                raise ResumeArtifactActionUnavailable
            now = _now()
            action = json.dumps(
                {"kind": kind, "acceptedAt": now}, separators=(",", ":"), sort_keys=True
            )
            connection.execute(
                """INSERT INTO resume_action_bindings VALUES(?,?,?,?,?)""",
                (idempotency_key, artifact_set_id, kind, expected_revision, now),
            )
            connection.execute(
                """UPDATE resume_artifact_sets SET active_action_json=?,revision=revision+1,
                updated_at=? WHERE artifact_set_id=?""",
                (action, now, artifact_set_id),
            )
            updated = connection.execute(
                "SELECT * FROM resume_artifact_sets WHERE artifact_set_id=?",
                (artifact_set_id,),
            ).fetchone()
            return self._artifact_snapshot(updated)

    def quarantines(self, *, limit: int, offset: int = 0) -> tuple[list[dict], int]:
        with self._connect() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM resume_artifact_sets WHERE quarantine_json IS NOT NULL"
            ).fetchone()[0]
            rows = connection.execute(
                """SELECT * FROM resume_artifact_sets WHERE quarantine_json IS NOT NULL
                ORDER BY updated_at DESC,artifact_set_id LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
            return [self._artifact_snapshot(row) for row in rows], total

    def pdf_record(self, artifact_set_id: str) -> tuple[str, str, str] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT pdf_path,pdf_digest,completion_json FROM resume_artifact_sets
                WHERE artifact_set_id=? AND disposition='sealed'""",
                (artifact_set_id,),
            ).fetchone()
            if not row or not row["pdf_path"] or not row["pdf_digest"]:
                return None
            completion = json.loads(row["completion_json"])
            return row["pdf_path"], row["pdf_digest"], completion["pdf"]["filename"]

    def _snapshot(self, connection: sqlite3.Connection, run_id: str) -> dict:
        run = connection.execute(
            "SELECT * FROM resume_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        candidates = connection.execute(
            "SELECT * FROM resume_candidates WHERE run_id=? ORDER BY ordinal", (run_id,)
        ).fetchall()
        verified = run["verified_cost_micros"]
        active = run["active_reservation_micros"]
        indeterminate = run["indeterminate_reservation_micros"]
        committed = verified + active + indeterminate
        candidate_values = [self._candidate_snapshot(row) for row in candidates]
        return {
            "runId": run["run_id"], "revision": run["revision"],
            "lifecycle": run["lifecycle"], "outcome": run["outcome"],
            "reasonCode": run["reason_code"], "target": run["target"],
            "attemptBudget": len(candidates), "createdAt": run["created_at"],
            "startedAt": run["started_at"], "stoppingDecidedAt": run["stopping_decided_at"],
            "finishedAt": run["finished_at"], "updatedAt": run["updated_at"],
            "progress": {
                "completions": sum(value["state"] == "completed" for value in candidate_values),
                "candidatesConsidered": sum(value["consideredAt"] is not None for value in candidate_values),
                "evaluationsConsumed": sum(value["evaluationConsumed"] for value in candidate_values),
            },
            "spend": {
                "ceilingMicros": run["spend_ceiling_micros"], "committedMicros": committed,
                "verifiedCostMicros": verified, "activeReservationMicros": active,
                "indeterminateReservationMicros": indeterminate,
                "remainingAuthorizedMicros": run["spend_ceiling_micros"] - committed,
            },
            "candidates": candidate_values,
        }

    @staticmethod
    def _candidate_snapshot(row: sqlite3.Row) -> dict:
        return {
            "applicationId": row["application_id"], "applicationLabel": row["application_label"],
            "ordinal": row["ordinal"], "state": row["state"], "stage": row["stage"],
            "reasonCode": row["reason_code"], "evaluationConsumed": bool(row["evaluation_consumed"]),
            "artifactSetId": row["artifact_set_id"],
            "completion": json.loads(row["completion_json"]) if row["completion_json"] else None,
            "consideredAt": row["considered_at"], "updatedAt": row["updated_at"],
            "terminalAt": row["terminal_at"],
        }

    @staticmethod
    def _artifact_snapshot(row: sqlite3.Row) -> dict:
        quarantine = json.loads(row["quarantine_json"]) if row["quarantine_json"] else None
        active_action = json.loads(row["active_action_json"]) if row["active_action_json"] else None
        available = []
        if quarantine and not active_action:
            available = ["reconcile"]
            if row["disposition"] == "compensation_required":
                available.append("compensate")
        return {
            "artifactSetId": row["artifact_set_id"], "runId": row["run_id"],
            "applicationId": row["application_id"], "candidateOrdinal": row["candidate_ordinal"],
            "applicationLabel": row["application_label"], "revision": row["revision"],
            "createdAt": row["created_at"], "updatedAt": row["updated_at"],
            "disposition": row["disposition"], "pendingBoundary": row["pending_boundary"],
            "quarantine": quarantine, "availableActions": available, "activeAction": active_action,
            "completion": json.loads(row["completion_json"]) if row["completion_json"] else None,
        }
