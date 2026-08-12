from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
from pathlib import Path
import re
import sqlite3
from typing import Callable, Iterator, Protocol, Sequence
from urllib.parse import urlsplit


ANALYSIS_SPEND_CEILING_MICROS = 500_000


class AnalysisRunLifecycle(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    FINISHED = "finished"


class AnalysisRunOutcome(str, Enum):
    TARGET_MET = "target_met"
    SPEND_LIMITED = "spend_limited"
    ATTEMPT_BUDGET_EXHAUSTED = "attempt_budget_exhausted"
    QUEUE_EXHAUSTED = "queue_exhausted"
    CANCELLED = "cancelled"
    AUTHORIZATION_BLOCKED = "authorization_blocked"
    FAILED = "failed"


class AnalysisCandidateState(str, Enum):
    PENDING = "pending"
    EVALUATING = "evaluating"
    ANALYZED = "analyzed"
    REPAIRED = "repaired"
    SKIPPED = "skipped"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"


class AnalysisProviderCallState(str, Enum):
    RESERVED = "reserved"
    DISPATCHING = "dispatching"
    SENT = "sent"
    RESPONSE_RECORDED = "response_recorded"
    SETTLED = "settled"
    RELEASED = "released"
    INDETERMINATE = "indeterminate"


TERMINAL_CANDIDATE_STATES = frozenset(
    {
        AnalysisCandidateState.ANALYZED,
        AnalysisCandidateState.REPAIRED,
        AnalysisCandidateState.SKIPPED,
        AnalysisCandidateState.FAILED,
        AnalysisCandidateState.INDETERMINATE,
    }
)

PROVIDER_CALL_TRANSITIONS = {
    AnalysisProviderCallState.RESERVED: frozenset(
        {
            AnalysisProviderCallState.DISPATCHING,
            AnalysisProviderCallState.RELEASED,
        }
    ),
    AnalysisProviderCallState.DISPATCHING: frozenset(
        {
            AnalysisProviderCallState.SENT,
            AnalysisProviderCallState.RESPONSE_RECORDED,
            AnalysisProviderCallState.RELEASED,
            AnalysisProviderCallState.INDETERMINATE,
        }
    ),
    AnalysisProviderCallState.SENT: frozenset(
        {
            AnalysisProviderCallState.RESPONSE_RECORDED,
            AnalysisProviderCallState.INDETERMINATE,
        }
    ),
    AnalysisProviderCallState.RESPONSE_RECORDED: frozenset(
        {
            AnalysisProviderCallState.SETTLED,
            AnalysisProviderCallState.INDETERMINATE,
        }
    ),
    AnalysisProviderCallState.SETTLED: frozenset(),
    AnalysisProviderCallState.RELEASED: frozenset(),
    AnalysisProviderCallState.INDETERMINATE: frozenset(),
}


class AnalysisRunStoreError(RuntimeError):
    pass


class AnalysisRunStoreUnavailableError(AnalysisRunStoreError):
    pass


class AnalysisRunNotFoundError(AnalysisRunStoreError):
    pass


class ActiveAnalysisRunError(AnalysisRunStoreError):
    def __init__(self, active_run_id: str):
        super().__init__("An Analysis Run is already active.")
        self.active_run_id = active_run_id


class AnalysisRunIdempotencyConflictError(AnalysisRunStoreError):
    pass


class InvalidAnalysisRunTransitionError(AnalysisRunStoreError):
    pass


class AnalysisRunLeaseError(AnalysisRunStoreError):
    pass


class ApplicationCallBudgetExhaustedError(AnalysisRunStoreError):
    pass


class ProviderDispatchBlockedError(AnalysisRunStoreError):
    pass


@dataclass(frozen=True)
class AnalysisCandidateSnapshot:
    application_id: str
    ordinal: int
    state: AnalysisCandidateState
    reason_code: str | None
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class AnalysisProviderAuthorizationMetadata:
    endpoint: str
    model: str
    approval_fingerprint: str
    request_fingerprint: str
    tokenizer_tokens: int
    utf8_bytes: int
    protocol_overhead_tokens: int
    input_cost_bound_tokens: int
    max_output_tokens: int
    cache_hit_input_micros_per_million_tokens: int
    cache_miss_input_micros_per_million_tokens: int
    output_micros_per_million_tokens: int

    def __post_init__(self) -> None:
        _safe_provider_endpoint(self.endpoint)
        _safe_provider_identity("model", self.model)
        _safe_provider_identity("approval fingerprint", self.approval_fingerprint)
        _safe_provider_identity("request fingerprint", self.request_fingerprint)
        for name in (
            "tokenizer_tokens",
            "utf8_bytes",
            "protocol_overhead_tokens",
            "input_cost_bound_tokens",
            "cache_hit_input_micros_per_million_tokens",
            "cache_miss_input_micros_per_million_tokens",
            "output_micros_per_million_tokens",
        ):
            _nonnegative_integer(name, getattr(self, name))
        _positive_integer("max_output_tokens", self.max_output_tokens)


@dataclass(frozen=True)
class AnalysisProviderSettlementMetadata:
    provider_request_id: str
    input_tokens: int
    output_tokens: int
    cache_hit_input_tokens: int
    cache_miss_input_tokens: int | None
    total_tokens: int | None
    reasoning_output_tokens: int | None
    finish_reason: str | None
    result_code: str

    def __post_init__(self) -> None:
        _safe_provider_identity("provider request", self.provider_request_id)
        _nonnegative_integer("input_tokens", self.input_tokens)
        _nonnegative_integer("output_tokens", self.output_tokens)
        _nonnegative_integer(
            "cache_hit_input_tokens", self.cache_hit_input_tokens
        )
        for name in (
            "cache_miss_input_tokens",
            "total_tokens",
            "reasoning_output_tokens",
        ):
            value = getattr(self, name)
            if value is not None:
                _nonnegative_integer(name, value)
        _safe_reason_code(self.finish_reason)
        if _safe_reason_code(self.result_code) is None:
            raise ValueError("Provider settlement requires a safe result code.")


@dataclass(frozen=True)
class AnalysisProviderCallSnapshot:
    call_id: str
    run_id: str
    application_id: str
    authorization_index: int
    transmission_index: int | None
    state: AnalysisProviderCallState
    reservation_micros: int
    verified_cost_micros: int | None
    created_at: datetime
    updated_at: datetime
    endpoint: str | None = None
    model: str | None = None
    approval_fingerprint: str | None = None
    request_fingerprint: str | None = None
    tokenizer_tokens: int | None = None
    utf8_bytes: int | None = None
    protocol_overhead_tokens: int | None = None
    input_cost_bound_tokens: int | None = None
    max_output_tokens: int | None = None
    cache_hit_input_micros_per_million_tokens: int | None = None
    cache_miss_input_micros_per_million_tokens: int | None = None
    output_micros_per_million_tokens: int | None = None
    provider_request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_hit_input_tokens: int | None = None
    cache_miss_input_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_output_tokens: int | None = None
    finish_reason: str | None = None
    result_code: str | None = None

    @property
    def call_index(self) -> int:
        """Compatibility alias for the authorization's caller-local index."""
        return self.authorization_index


@dataclass(frozen=True)
class AnalysisRunSnapshot:
    run_id: str
    lifecycle: AnalysisRunLifecycle
    outcome: AnalysisRunOutcome | None
    reason_code: str | None
    target: int
    attempt_budget: int
    candidate_set_truncated: bool
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    lease_owner: str | None
    lease_expires_at: datetime | None
    completion_count: int
    repaired_count: int
    evaluated_count: int
    skipped_count: int
    failed_count: int
    indeterminate_count: int
    spend_ceiling_micros: int
    committed_spend_micros: int
    verified_cost_micros: int
    active_reservation_micros: int
    indeterminate_reservation_micros: int
    remaining_authorized_micros: int
    candidates: tuple[AnalysisCandidateSnapshot, ...]


class AnalysisRunStore(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def transactional(self) -> bool: ...

    @property
    def error(self) -> str | None: ...

    def reserve_provider_call(
        self,
        *,
        run_id: str,
        application_id: str,
        call_id: str,
        call_index: int,
        reservation_micros: int,
        authorization: AnalysisProviderAuthorizationMetadata,
        lease_owner: str,
    ) -> AnalysisProviderCallSnapshot | None: ...

    def claim_recoverable_run(
        self,
        *,
        lease_owner: str,
        lease_expires_at: datetime,
    ) -> AnalysisRunSnapshot | None: ...

    def renew_lease(
        self,
        run_id: str,
        *,
        lease_owner: str,
        lease_expires_at: datetime,
    ) -> AnalysisRunSnapshot: ...

    def protect_remote_commit(
        self,
        run_id: str,
        *,
        lease_owner: str,
        minimum_duration: timedelta,
    ) -> AnalysisRunSnapshot: ...

    def relinquish_lease(
        self, run_id: str, *, lease_owner: str
    ) -> AnalysisRunSnapshot: ...

    def claim_next_candidate(
        self, run_id: str, *, lease_owner: str
    ) -> AnalysisCandidateSnapshot | None: ...

    def request_cancellation(self, run_id: str) -> AnalysisRunSnapshot: ...

    def record_run_reason(
        self, run_id: str, reason_code: str, *, lease_owner: str
    ) -> AnalysisRunSnapshot: ...

    def list_recoverable_runs(self) -> tuple[AnalysisRunSnapshot, ...]: ...

    def reconcile_interrupted_provider_calls(
        self, run_id: str, *, lease_owner: str
    ) -> tuple[AnalysisProviderCallSnapshot, ...]: ...

    def begin_provider_dispatch(
        self, call_id: str, *, lease_owner: str
    ) -> AnalysisProviderCallSnapshot: ...

    def record_provider_call_response(
        self,
        call_id: str,
        metadata: AnalysisProviderSettlementMetadata,
        *,
        lease_owner: str,
    ) -> AnalysisProviderCallSnapshot: ...

    def quarantine_commit_unknown(
        self, run_id: str, application_id: str, *, lease_owner: str
    ) -> None: ...

    def clear_commit_quarantine(self, application_id: str) -> None: ...

    def list_commit_quarantines(self) -> tuple[str, ...]: ...


class SqliteAnalysisRunStore:
    """Durable Applications-owned coordination metadata for Analysis Runs."""

    SCHEMA_VERSION = 7

    def __init__(
        self,
        path: Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self._path = Path(path)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @property
    def available(self) -> bool:
        return True

    @property
    def transactional(self) -> bool:
        return True

    @property
    def error(self) -> None:
        return None

    def _connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(
                self._path,
                timeout=5,
                isolation_level=None,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            return connection
        except sqlite3.Error as error:
            raise AnalysisRunStoreError(
                "The Analysis Run Store is unavailable."
            ) from error

    @contextmanager
    def _read_connection(self) -> Iterator[sqlite3.Connection]:
        connection = None
        try:
            connection = self._connect()
            yield connection
        except sqlite3.Error as error:
            raise AnalysisRunStoreError(
                "The Analysis Run Store query failed."
            ) from error
        finally:
            if connection is not None:
                connection.close()

    def _initialize(self) -> None:
        with self._read_connection() as connection:
            journal_mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            if str(journal_mode).lower() not in {"wal", "memory"}:
                raise AnalysisRunStoreError(
                    "The Analysis Run Store does not support transactional writes."
                )
            connection.execute("BEGIN IMMEDIATE")
            previous_schema_version = connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
            _recover_interrupted_provider_call_migration(connection)
            _execute_sql_script(
                connection,
                """
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    run_id TEXT PRIMARY KEY NOT NULL,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    target INTEGER NOT NULL
                        CHECK (typeof(target) = 'integer' AND target BETWEEN 1 AND 10),
                    lifecycle TEXT NOT NULL
                        CHECK (lifecycle IN ('queued', 'running', 'cancelling', 'finished')),
                    outcome TEXT
                        CHECK (outcome IS NULL OR outcome IN (
                            'target_met',
                            'spend_limited',
                            'attempt_budget_exhausted',
                            'queue_exhausted',
                            'cancelled',
                            'authorization_blocked',
                            'failed'
                        )),
                    reason_code TEXT CHECK (
                        reason_code IS NULL
                        OR (
                            length(reason_code) BETWEEN 1 AND 64
                            AND substr(reason_code, 1, 1) BETWEEN 'a' AND 'z'
                            AND reason_code NOT GLOB '*[^a-z0-9_]*'
                        )
                    ),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    lease_owner TEXT,
                    lease_expires_at TEXT,
                    attempt_budget INTEGER NOT NULL
                        CHECK (
                            typeof(attempt_budget) = 'integer'
                            AND attempt_budget BETWEEN 0 AND 20
                        ),
                    candidate_set_truncated INTEGER NOT NULL DEFAULT 0
                        CHECK (candidate_set_truncated IN (0, 1)),
                    completion_count INTEGER NOT NULL DEFAULT 0 CHECK (completion_count >= 0),
                    repaired_count INTEGER NOT NULL DEFAULT 0 CHECK (repaired_count >= 0),
                    evaluated_count INTEGER NOT NULL DEFAULT 0 CHECK (evaluated_count >= 0),
                    skipped_count INTEGER NOT NULL DEFAULT 0 CHECK (skipped_count >= 0),
                    failed_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
                    indeterminate_count INTEGER NOT NULL DEFAULT 0 CHECK (indeterminate_count >= 0),
                    active_guard INTEGER NOT NULL DEFAULT 1 CHECK (active_guard = 1),
                    CHECK (
                        (lifecycle = 'finished' AND outcome IS NOT NULL AND finished_at IS NOT NULL)
                        OR
                        (lifecycle <> 'finished' AND outcome IS NULL AND finished_at IS NULL)
                    )
                );

                CREATE UNIQUE INDEX IF NOT EXISTS one_active_analysis_run
                    ON analysis_runs(active_guard)
                    WHERE lifecycle <> 'finished';

                CREATE TABLE IF NOT EXISTS analysis_run_candidates (
                    run_id TEXT NOT NULL REFERENCES analysis_runs(run_id) ON DELETE CASCADE,
                    application_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
                    state TEXT NOT NULL DEFAULT 'pending'
                        CHECK (state IN (
                            'pending',
                            'evaluating',
                            'analyzed',
                            'repaired',
                            'skipped',
                            'failed',
                            'indeterminate'
                        )),
                    reason_code TEXT CHECK (
                        reason_code IS NULL
                        OR (
                            length(reason_code) BETWEEN 1 AND 64
                            AND substr(reason_code, 1, 1) BETWEEN 'a' AND 'z'
                            AND reason_code NOT GLOB '*[^a-z0-9_]*'
                        )
                    ),
                    started_at TEXT,
                    completed_at TEXT,
                    PRIMARY KEY (run_id, application_id),
                    UNIQUE (run_id, ordinal)
                );

                CREATE TABLE IF NOT EXISTS analysis_provider_calls (
                    call_id TEXT PRIMARY KEY NOT NULL,
                    run_id TEXT NOT NULL,
                    application_id TEXT NOT NULL,
                    authorization_index INTEGER NOT NULL
                        CHECK (
                            typeof(authorization_index) = 'integer'
                            AND authorization_index > 0
                        ),
                    transmission_index INTEGER
                        CHECK (
                            transmission_index IS NULL
                            OR (
                                typeof(transmission_index) = 'integer'
                                AND transmission_index BETWEEN 1 AND 3
                            )
                        ),
                    state TEXT NOT NULL
                        CHECK (state IN (
                            'reserved',
                            'dispatching',
                            'sent',
                            'response_recorded',
                            'settled',
                            'released',
                            'indeterminate'
                        )),
                    reservation_micros INTEGER NOT NULL
                        CHECK (
                            typeof(reservation_micros) = 'integer'
                            AND reservation_micros > 0
                        ),
                    verified_cost_micros INTEGER
                        CHECK (
                            verified_cost_micros IS NULL
                            OR (
                                typeof(verified_cost_micros) = 'integer'
                                AND verified_cost_micros BETWEEN 0 AND reservation_micros
                            )
                        ),
                    endpoint TEXT CHECK (endpoint IS NULL OR length(endpoint) <= 2048),
                    model TEXT CHECK (model IS NULL OR length(model) <= 255),
                    approval_fingerprint TEXT
                        CHECK (approval_fingerprint IS NULL OR length(approval_fingerprint) <= 255),
                    request_fingerprint TEXT
                        CHECK (request_fingerprint IS NULL OR length(request_fingerprint) <= 255),
                    tokenizer_tokens INTEGER CHECK (tokenizer_tokens IS NULL OR tokenizer_tokens >= 0),
                    utf8_bytes INTEGER CHECK (utf8_bytes IS NULL OR utf8_bytes >= 0),
                    protocol_overhead_tokens INTEGER
                        CHECK (protocol_overhead_tokens IS NULL OR protocol_overhead_tokens >= 0),
                    input_cost_bound_tokens INTEGER
                        CHECK (input_cost_bound_tokens IS NULL OR input_cost_bound_tokens >= 0),
                    max_output_tokens INTEGER
                        CHECK (max_output_tokens IS NULL OR max_output_tokens > 0),
                    cache_hit_input_micros_per_million_tokens INTEGER
                        CHECK (
                            cache_hit_input_micros_per_million_tokens IS NULL
                            OR cache_hit_input_micros_per_million_tokens >= 0
                        ),
                    cache_miss_input_micros_per_million_tokens INTEGER
                        CHECK (
                            cache_miss_input_micros_per_million_tokens IS NULL
                            OR cache_miss_input_micros_per_million_tokens >= 0
                        ),
                    output_micros_per_million_tokens INTEGER
                        CHECK (
                            output_micros_per_million_tokens IS NULL
                            OR output_micros_per_million_tokens >= 0
                        ),
                    provider_request_id TEXT
                        CHECK (provider_request_id IS NULL OR length(provider_request_id) <= 255),
                    input_tokens INTEGER CHECK (input_tokens IS NULL OR input_tokens >= 0),
                    output_tokens INTEGER CHECK (output_tokens IS NULL OR output_tokens >= 0),
                    cache_hit_input_tokens INTEGER
                        CHECK (cache_hit_input_tokens IS NULL OR cache_hit_input_tokens >= 0),
                    cache_miss_input_tokens INTEGER
                        CHECK (cache_miss_input_tokens IS NULL OR cache_miss_input_tokens >= 0),
                    total_tokens INTEGER
                        CHECK (total_tokens IS NULL OR total_tokens >= 0),
                    reasoning_output_tokens INTEGER
                        CHECK (reasoning_output_tokens IS NULL OR reasoning_output_tokens >= 0),
                    finish_reason TEXT CHECK (finish_reason IS NULL OR length(finish_reason) <= 64),
                    result_code TEXT CHECK (result_code IS NULL OR length(result_code) <= 64),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (run_id, application_id)
                        REFERENCES analysis_run_candidates(run_id, application_id)
                        ON DELETE CASCADE,
                    CHECK (
                        (state = 'settled' AND verified_cost_micros IS NOT NULL)
                        OR (state <> 'settled' AND verified_cost_micros IS NULL)
                    )
                );

                CREATE UNIQUE INDEX IF NOT EXISTS one_evaluating_candidate_per_run
                    ON analysis_run_candidates(run_id)
                    WHERE state = 'evaluating';

                CREATE TABLE IF NOT EXISTS analysis_commit_quarantine (
                    application_id TEXT PRIMARY KEY NOT NULL,
                    run_id TEXT NOT NULL REFERENCES analysis_runs(run_id),
                    created_at TEXT NOT NULL
                );
                """
            )
            run_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(analysis_runs)")
            }
            if "reason_code" not in run_columns:
                connection.execute(
                    """
                    ALTER TABLE analysis_runs
                    ADD COLUMN reason_code TEXT CHECK (
                        reason_code IS NULL
                        OR (
                            length(reason_code) BETWEEN 1 AND 64
                            AND substr(reason_code, 1, 1) BETWEEN 'a' AND 'z'
                            AND reason_code NOT GLOB '*[^a-z0-9_]*'
                        )
                    )
                    """
                )
            if "candidate_set_truncated" not in run_columns:
                connection.execute(
                    """
                    ALTER TABLE analysis_runs
                    ADD COLUMN candidate_set_truncated INTEGER NOT NULL DEFAULT 0
                        CHECK (candidate_set_truncated IN (0, 1))
                    """
                )
            call_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(analysis_provider_calls)"
                )
            }
            if "transmission_index" not in call_columns:
                connection.execute(
                    "ALTER TABLE analysis_provider_calls RENAME TO analysis_provider_calls_v2"
                )
                _execute_sql_script(
                    connection,
                    """
                    CREATE TABLE analysis_provider_calls (
                        call_id TEXT PRIMARY KEY NOT NULL,
                        run_id TEXT NOT NULL,
                        application_id TEXT NOT NULL,
                        authorization_index INTEGER NOT NULL
                            CHECK (
                                typeof(authorization_index) = 'integer'
                                AND authorization_index > 0
                            ),
                        transmission_index INTEGER
                            CHECK (
                                transmission_index IS NULL
                                OR (
                                    typeof(transmission_index) = 'integer'
                                    AND transmission_index BETWEEN 1 AND 3
                                )
                            ),
                        state TEXT NOT NULL
                            CHECK (state IN (
                                'reserved',
                                'dispatching',
                                'sent',
                                'response_recorded',
                                'settled',
                                'released',
                                'indeterminate'
                            )),
                        reservation_micros INTEGER NOT NULL
                            CHECK (
                                typeof(reservation_micros) = 'integer'
                                AND reservation_micros > 0
                            ),
                        verified_cost_micros INTEGER
                            CHECK (
                                verified_cost_micros IS NULL
                                OR (
                                    typeof(verified_cost_micros) = 'integer'
                                    AND verified_cost_micros
                                        BETWEEN 0 AND reservation_micros
                                )
                            ),
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (run_id, application_id)
                            REFERENCES analysis_run_candidates(run_id, application_id)
                            ON DELETE CASCADE,
                        CHECK (
                            (state = 'settled' AND verified_cost_micros IS NOT NULL)
                            OR (state <> 'settled' AND verified_cost_micros IS NULL)
                        )
                    );

                    INSERT INTO analysis_provider_calls (
                        call_id,
                        run_id,
                        application_id,
                        authorization_index,
                        transmission_index,
                        state,
                        reservation_micros,
                        verified_cost_micros,
                        created_at,
                        updated_at
                    )
                    SELECT
                        call_id,
                        run_id,
                        application_id,
                        call_index,
                        CASE
                            WHEN state IN ('reserved', 'released') THEN NULL
                            ELSE call_index
                        END,
                        state,
                        reservation_micros,
                        verified_cost_micros,
                        created_at,
                        updated_at
                    FROM analysis_provider_calls_v2;

                    DROP TABLE analysis_provider_calls_v2;
                    """
                )
            call_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(analysis_provider_calls)"
                )
            }
            metadata_columns = {
                "endpoint": "TEXT CHECK (endpoint IS NULL OR length(endpoint) <= 2048)",
                "model": "TEXT CHECK (model IS NULL OR length(model) <= 255)",
                "approval_fingerprint": (
                    "TEXT CHECK (approval_fingerprint IS NULL "
                    "OR length(approval_fingerprint) <= 255)"
                ),
                "request_fingerprint": (
                    "TEXT CHECK (request_fingerprint IS NULL "
                    "OR length(request_fingerprint) <= 255)"
                ),
                "tokenizer_tokens": (
                    "INTEGER CHECK (tokenizer_tokens IS NULL OR tokenizer_tokens >= 0)"
                ),
                "utf8_bytes": "INTEGER CHECK (utf8_bytes IS NULL OR utf8_bytes >= 0)",
                "protocol_overhead_tokens": (
                    "INTEGER CHECK (protocol_overhead_tokens IS NULL "
                    "OR protocol_overhead_tokens >= 0)"
                ),
                "input_cost_bound_tokens": (
                    "INTEGER CHECK (input_cost_bound_tokens IS NULL "
                    "OR input_cost_bound_tokens >= 0)"
                ),
                "max_output_tokens": (
                    "INTEGER CHECK (max_output_tokens IS NULL OR max_output_tokens > 0)"
                ),
                "cache_hit_input_micros_per_million_tokens": (
                    "INTEGER CHECK (cache_hit_input_micros_per_million_tokens IS NULL "
                    "OR cache_hit_input_micros_per_million_tokens >= 0)"
                ),
                "cache_miss_input_micros_per_million_tokens": (
                    "INTEGER CHECK (cache_miss_input_micros_per_million_tokens IS NULL "
                    "OR cache_miss_input_micros_per_million_tokens >= 0)"
                ),
                "output_micros_per_million_tokens": (
                    "INTEGER CHECK (output_micros_per_million_tokens IS NULL "
                    "OR output_micros_per_million_tokens >= 0)"
                ),
                "provider_request_id": (
                    "TEXT CHECK (provider_request_id IS NULL "
                    "OR length(provider_request_id) <= 255)"
                ),
                "input_tokens": (
                    "INTEGER CHECK (input_tokens IS NULL OR input_tokens >= 0)"
                ),
                "output_tokens": (
                    "INTEGER CHECK (output_tokens IS NULL OR output_tokens >= 0)"
                ),
                "cache_hit_input_tokens": (
                    "INTEGER CHECK (cache_hit_input_tokens IS NULL "
                    "OR cache_hit_input_tokens >= 0)"
                ),
                "cache_miss_input_tokens": (
                    "INTEGER CHECK (cache_miss_input_tokens IS NULL "
                    "OR cache_miss_input_tokens >= 0)"
                ),
                "total_tokens": (
                    "INTEGER CHECK (total_tokens IS NULL OR total_tokens >= 0)"
                ),
                "reasoning_output_tokens": (
                    "INTEGER CHECK (reasoning_output_tokens IS NULL "
                    "OR reasoning_output_tokens >= 0)"
                ),
                "finish_reason": (
                    "TEXT CHECK (finish_reason IS NULL OR length(finish_reason) <= 64)"
                ),
                "result_code": (
                    "TEXT CHECK (result_code IS NULL OR length(result_code) <= 64)"
                ),
            }
            for column_name, column_definition in metadata_columns.items():
                if column_name not in call_columns:
                    connection.execute(
                        f"ALTER TABLE analysis_provider_calls "
                        f"ADD COLUMN {column_name} {column_definition}"
                    )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS unique_analysis_transmission_slot
                ON analysis_provider_calls(run_id, application_id, transmission_index)
                WHERE transmission_index IS NOT NULL
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS one_analysis_call_in_flight
                ON analysis_provider_calls(run_id)
                WHERE state IN ('dispatching', 'sent', 'response_recorded')
                """
            )
            if previous_schema_version < 5:
                for row in connection.execute(
                    "SELECT run_id, idempotency_key FROM analysis_runs"
                ):
                    if not _is_idempotency_digest(row["idempotency_key"]):
                        connection.execute(
                            "UPDATE analysis_runs SET idempotency_key = ? WHERE run_id = ?",
                            (
                                _idempotency_digest(row["idempotency_key"]),
                                row["run_id"],
                            ),
                        )
            connection.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
            connection.commit()

    @contextmanager
    def _write_transaction(self) -> Iterator[sqlite3.Connection]:
        connection = None
        try:
            connection = self._connect()
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except sqlite3.Error as error:
            if connection is not None:
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
            raise AnalysisRunStoreError(
                "The Analysis Run Store transaction failed."
            ) from error
        except BaseException:
            if connection is not None:
                connection.rollback()
            raise
        finally:
            if connection is not None:
                connection.close()

    def create_run(
        self,
        *,
        run_id: str,
        idempotency_key: str,
        target: int,
        candidate_ids: Sequence[str],
        candidate_set_truncated: bool = False,
    ) -> AnalysisRunSnapshot:
        run_id = _require_identity("run_id", run_id)
        idempotency_key = _idempotency_digest(idempotency_key)
        candidate_ids = tuple(
            _require_identity("candidate_id", candidate_id)
            for candidate_id in candidate_ids
        )
        if type(target) is not int or not 1 <= target <= 10:
            raise ValueError("Analysis Batch Target must be an integer from 1 through 10.")
        if type(candidate_set_truncated) is not bool:
            raise ValueError("Candidate Set truncation must be a boolean.")
        if len(candidate_ids) > 20:
            raise ValueError("An Analysis Run may contain at most 20 candidates.")
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("An Analysis Run candidate identity may appear only once.")
        now = _timestamp(self._clock())

        with self._write_transaction() as connection:
            existing = connection.execute(
                "SELECT run_id, target FROM analysis_runs WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                if existing["target"] != target:
                    raise AnalysisRunIdempotencyConflictError(
                        "The idempotency key already identifies a different target."
                    )
                return self._snapshot(connection, existing["run_id"])
            try:
                connection.execute(
                    """
                    INSERT INTO analysis_runs (
                        run_id,
                        idempotency_key,
                        target,
                        lifecycle,
                        created_at,
                        updated_at,
                        attempt_budget,
                        candidate_set_truncated
                    ) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        idempotency_key,
                        target,
                        now,
                        now,
                        len(candidate_ids),
                        int(candidate_set_truncated),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                active = connection.execute(
                    "SELECT run_id FROM analysis_runs WHERE lifecycle <> 'finished'"
                ).fetchone()
                if active is not None:
                    raise ActiveAnalysisRunError(active["run_id"]) from exc
                raise AnalysisRunStoreError(
                    "The Analysis Run identity is already in use."
                ) from exc
            connection.executemany(
                """
                INSERT INTO analysis_run_candidates (
                    run_id,
                    application_id,
                    ordinal
                ) VALUES (?, ?, ?)
                """,
                (
                    (run_id, application_id, ordinal)
                    for ordinal, application_id in enumerate(candidate_ids)
                ),
            )
            return self._snapshot(connection, run_id)

    def assert_current_lease(
        self,
        run_id: str,
        *,
        lease_owner: str,
        allow_cancelling: bool = True,
    ) -> None:
        if type(allow_cancelling) is not bool:
            raise TypeError("Lease lifecycle policy must be a boolean.")
        with self._read_connection() as connection:
            self._assert_current_lease(
                connection,
                run_id,
                lease_owner=lease_owner,
                allow_cancelling=allow_cancelling,
            )

    def get_run(self, run_id: str) -> AnalysisRunSnapshot | None:
        with self._read_connection() as connection:
            if not connection.execute(
                "SELECT 1 FROM analysis_runs WHERE run_id = ?", (run_id,)
            ).fetchone():
                return None
            return self._snapshot(connection, run_id)

    def get_by_idempotency_key(
        self, idempotency_key: str
    ) -> AnalysisRunSnapshot | None:
        idempotency_key = _idempotency_digest(idempotency_key)
        with self._read_connection() as connection:
            row = connection.execute(
                "SELECT run_id FROM analysis_runs WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            return None if row is None else self._snapshot(connection, row["run_id"])

    def get_active_run(self) -> AnalysisRunSnapshot | None:
        with self._read_connection() as connection:
            row = connection.execute(
                "SELECT run_id FROM analysis_runs WHERE lifecycle <> 'finished'"
            ).fetchone()
            return None if row is None else self._snapshot(connection, row["run_id"])

    def list_recoverable_runs(self) -> tuple[AnalysisRunSnapshot, ...]:
        now = _timestamp(self._clock())
        with self._read_connection() as connection:
            return tuple(
                self._snapshot(connection, row["run_id"])
                for row in connection.execute(
                    """
                    SELECT run_id
                    FROM analysis_runs
                    WHERE lifecycle = 'queued'
                       OR (
                            lifecycle IN ('running', 'cancelling')
                            AND (lease_expires_at IS NULL OR lease_expires_at <= ?)
                       )
                    ORDER BY created_at, run_id
                    """,
                    (now,),
                )
            )

    def claim_recoverable_run(
        self,
        *,
        lease_owner: str,
        lease_expires_at: datetime,
    ) -> AnalysisRunSnapshot | None:
        lease_owner = _require_identity("lease_owner", lease_owner)
        now_value = self._clock()
        now = _timestamp(now_value)
        lease_expires = _future_timestamp(lease_expires_at, after=now_value)
        with self._write_transaction() as connection:
            row = connection.execute(
                """
                SELECT run_id, lifecycle
                FROM analysis_runs
                WHERE lifecycle <> 'finished'
                  AND (
                    lifecycle = 'queued'
                    OR lease_expires_at IS NULL
                    OR lease_expires_at <= ?
                  )
                ORDER BY created_at, run_id
                LIMIT 1
                """,
                (now,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                UPDATE analysis_runs
                SET lifecycle = CASE
                        WHEN lifecycle = 'queued' THEN 'running'
                        ELSE lifecycle
                    END,
                    started_at = COALESCE(started_at, ?),
                    updated_at = ?,
                    lease_owner = ?,
                    lease_expires_at = CASE
                        WHEN lease_expires_at IS NOT NULL
                             AND lease_expires_at > ?
                        THEN lease_expires_at
                        ELSE ?
                    END
                WHERE run_id = ?
                """,
                (
                    now,
                    now,
                    lease_owner,
                    lease_expires,
                    lease_expires,
                    row["run_id"],
                ),
            )
            return self._snapshot(connection, row["run_id"])

    def start_run(
        self,
        run_id: str,
        *,
        lease_owner: str,
        lease_expires_at: datetime,
    ) -> AnalysisRunSnapshot:
        lease_owner = _require_identity("lease_owner", lease_owner)
        now_value = self._clock()
        now = _timestamp(now_value)
        lease_expires = _future_timestamp(lease_expires_at, after=now_value)
        with self._write_transaction() as connection:
            current = self._require_run(connection, run_id)
            if current["lifecycle"] not in {
                AnalysisRunLifecycle.QUEUED.value,
                AnalysisRunLifecycle.RUNNING.value,
            }:
                raise InvalidAnalysisRunTransitionError(
                    "Only a queued or running Analysis Run can receive a worker lease."
                )
            if (
                current["lifecycle"] == AnalysisRunLifecycle.RUNNING.value
                and current["lease_owner"] not in {None, lease_owner}
                and current["lease_expires_at"] is not None
                and current["lease_expires_at"] > now
            ):
                raise AnalysisRunLeaseError(
                    "The Analysis Run lease is owned by another worker."
                )
            connection.execute(
                """
                UPDATE analysis_runs
                SET lifecycle = 'running',
                    started_at = COALESCE(started_at, ?),
                    updated_at = ?,
                    lease_owner = ?,
                    lease_expires_at = ?
                WHERE run_id = ?
                """,
                (now, now, lease_owner, lease_expires, run_id),
            )
            return self._snapshot(connection, run_id)

    def renew_lease(
        self,
        run_id: str,
        *,
        lease_owner: str,
        lease_expires_at: datetime,
    ) -> AnalysisRunSnapshot:
        lease_owner = _require_identity("lease_owner", lease_owner)
        now_value = self._clock()
        now = _timestamp(now_value)
        lease_expires = _future_timestamp(lease_expires_at, after=now_value)
        with self._write_transaction() as connection:
            current = self._require_run(connection, run_id)
            if current["lifecycle"] not in {
                AnalysisRunLifecycle.RUNNING.value,
                AnalysisRunLifecycle.CANCELLING.value,
            }:
                raise InvalidAnalysisRunTransitionError(
                    "Only a running or cancelling Analysis Run has a renewable lease."
                )
            if current["lease_owner"] != lease_owner:
                raise AnalysisRunLeaseError(
                    "The Analysis Run lease is owned by another worker."
                )
            if (
                current["lease_expires_at"] is None
                or current["lease_expires_at"] <= now
            ):
                raise AnalysisRunLeaseError(
                    "The Analysis Run lease has expired and must be reclaimed."
                )
            lease_expires = max(
                lease_expires,
                current["lease_expires_at"],
            )
            connection.execute(
                """
                UPDATE analysis_runs
                SET updated_at = ?, lease_expires_at = ?
                WHERE run_id = ?
                """,
                (now, lease_expires, run_id),
            )
            return self._snapshot(connection, run_id)

    def protect_remote_commit(
        self,
        run_id: str,
        *,
        lease_owner: str,
        minimum_duration: timedelta,
    ) -> AnalysisRunSnapshot:
        """Keep one worker authoritative for a bounded remote commit window."""
        if (
            not isinstance(minimum_duration, timedelta)
            or minimum_duration <= timedelta(0)
        ):
            raise ValueError("Remote commit protection must be a positive duration.")
        return self.renew_lease(
            run_id,
            lease_owner=lease_owner,
            lease_expires_at=self._clock() + minimum_duration,
        )

    def relinquish_lease(
        self, run_id: str, *, lease_owner: str
    ) -> AnalysisRunSnapshot:
        """Make unfinished work immediately reclaimable on graceful shutdown."""
        lease_owner = _require_identity("lease_owner", lease_owner)
        now = _timestamp(self._clock())
        with self._write_transaction() as connection:
            current = self._require_run(connection, run_id)
            if current["lifecycle"] == AnalysisRunLifecycle.FINISHED.value:
                return self._snapshot(connection, run_id)
            if current["lease_owner"] not in {None, lease_owner}:
                raise AnalysisRunLeaseError(
                    "The Analysis Run lease is owned by another worker."
                )
            connection.execute(
                """
                UPDATE analysis_runs
                SET updated_at = ?, lease_owner = NULL, lease_expires_at = NULL
                WHERE run_id = ?
                """,
                (now, run_id),
            )
            return self._snapshot(connection, run_id)

    def claim_next_candidate(
        self, run_id: str, *, lease_owner: str
    ) -> AnalysisCandidateSnapshot | None:
        lease_owner = _require_identity("lease_owner", lease_owner)
        now = _timestamp(self._clock())
        with self._write_transaction() as connection:
            run = self._require_run(connection, run_id)
            if run["lifecycle"] != AnalysisRunLifecycle.RUNNING.value:
                return None
            if run["lease_owner"] != lease_owner:
                raise AnalysisRunLeaseError(
                    "The Analysis Run lease is owned by another worker."
                )
            if run["lease_expires_at"] is None or run["lease_expires_at"] <= now:
                raise AnalysisRunLeaseError("The Analysis Run lease has expired.")
            candidate = connection.execute(
                """
                SELECT *
                FROM analysis_run_candidates
                WHERE run_id = ? AND state = 'evaluating'
                ORDER BY ordinal
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            if candidate is None:
                candidate = connection.execute(
                    """
                    SELECT *
                    FROM analysis_run_candidates
                    WHERE run_id = ? AND state = 'pending'
                    ORDER BY ordinal
                    LIMIT 1
                    """,
                    (run_id,),
                ).fetchone()
                if candidate is None:
                    return None
                connection.execute(
                    """
                    UPDATE analysis_run_candidates
                    SET state = 'evaluating', started_at = ?
                    WHERE run_id = ? AND application_id = ? AND state = 'pending'
                    """,
                    (now, run_id, candidate["application_id"]),
                )
                candidate = connection.execute(
                    """
                    SELECT *
                    FROM analysis_run_candidates
                    WHERE run_id = ? AND application_id = ?
                    """,
                    (run_id, candidate["application_id"]),
                ).fetchone()
            return self._candidate_from_row(candidate)

    def request_cancellation(self, run_id: str) -> AnalysisRunSnapshot:
        now = _timestamp(self._clock())
        with self._write_transaction() as connection:
            current = self._require_run(connection, run_id)
            if current["lifecycle"] in {
                AnalysisRunLifecycle.CANCELLING.value,
                AnalysisRunLifecycle.FINISHED.value,
            }:
                return self._snapshot(connection, run_id)
            connection.execute(
                """
                UPDATE analysis_runs
                SET lifecycle = 'cancelling', updated_at = ?
                WHERE run_id = ?
                """,
                (now, run_id),
            )
            return self._snapshot(connection, run_id)

    def record_run_reason(
        self, run_id: str, reason_code: str, *, lease_owner: str
    ) -> AnalysisRunSnapshot:
        reason_code = _safe_reason_code(reason_code)
        now = _timestamp(self._clock())
        with self._write_transaction() as connection:
            current = self._assert_current_lease(
                connection,
                run_id,
                lease_owner=lease_owner,
                allow_cancelling=True,
            )
            if current["reason_code"] is not None:
                if current["reason_code"] != reason_code:
                    raise InvalidAnalysisRunTransitionError(
                        "An Analysis Run reason cannot be replaced."
                    )
                return self._snapshot(connection, run_id)
            if current["lifecycle"] == AnalysisRunLifecycle.FINISHED.value:
                raise InvalidAnalysisRunTransitionError(
                    "A finished Analysis Run reason cannot be replaced."
                )
            connection.execute(
                """
                UPDATE analysis_runs
                SET reason_code = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (reason_code, now, run_id),
            )
            return self._snapshot(connection, run_id)

    def record_candidate_result(
        self,
        run_id: str,
        application_id: str,
        state: AnalysisCandidateState,
        *,
        reason_code: str | None = None,
        stop_outcome: AnalysisRunOutcome | None = None,
        stop_reason_code: str | None = None,
        lease_owner: str,
    ) -> AnalysisRunSnapshot:
        if state not in TERMINAL_CANDIDATE_STATES:
            raise ValueError("A candidate result must be a terminal candidate state.")
        reason_code = _safe_reason_code(reason_code)
        stop_reason_code = _safe_reason_code(stop_reason_code)
        if (stop_outcome is None) != (stop_reason_code is None):
            raise ValueError(
                "A run-scoped candidate result requires an outcome and reason code."
            )
        now = _timestamp(self._clock())
        with self._write_transaction() as connection:
            self._assert_current_lease(
                connection,
                run_id,
                lease_owner=lease_owner,
                allow_cancelling=True,
            )
            candidate = connection.execute(
                """
                SELECT state, reason_code
                FROM analysis_run_candidates
                WHERE run_id = ? AND application_id = ?
                """,
                (run_id, application_id),
            ).fetchone()
            if candidate is None:
                raise AnalysisRunStoreError(
                    "The Application is not part of this Analysis Run."
                )
            current_state = AnalysisCandidateState(candidate["state"])
            if current_state in TERMINAL_CANDIDATE_STATES:
                if current_state is not state or candidate["reason_code"] != reason_code:
                    raise InvalidAnalysisRunTransitionError(
                        "A completed candidate result cannot be replaced."
                    )
                snapshot = self._snapshot(connection, run_id)
                if stop_outcome is None or snapshot.lifecycle is AnalysisRunLifecycle.FINISHED:
                    return snapshot
            else:
                connection.execute(
                    """
                    UPDATE analysis_run_candidates
                    SET state = ?, reason_code = ?, completed_at = ?
                    WHERE run_id = ? AND application_id = ?
                    """,
                    (state.value, reason_code, now, run_id, application_id),
                )
                self._refresh_progress(connection, run_id, now)
            if stop_outcome is not None:
                run = self._require_run(connection, run_id)
                effective_outcome = stop_outcome
                effective_reason = stop_reason_code
                if run["lifecycle"] == AnalysisRunLifecycle.CANCELLING.value:
                    effective_outcome = AnalysisRunOutcome.CANCELLED
                    effective_reason = "cancelled"
                active_call = connection.execute(
                    """
                    SELECT 1 FROM analysis_provider_calls
                    WHERE run_id = ?
                      AND state IN (
                          'reserved', 'dispatching', 'sent', 'response_recorded'
                      )
                    LIMIT 1
                    """,
                    (run_id,),
                ).fetchone()
                if active_call is not None:
                    raise InvalidAnalysisRunTransitionError(
                        "A run-scoped candidate result cannot finish with an active provider call."
                    )
                connection.execute(
                    """
                    UPDATE analysis_runs
                    SET lifecycle = 'finished', outcome = ?, reason_code = ?,
                        updated_at = ?, finished_at = ?,
                        lease_owner = NULL, lease_expires_at = NULL
                    WHERE run_id = ?
                    """,
                    (
                        effective_outcome.value,
                        effective_reason,
                        now,
                        now,
                        run_id,
                    ),
                )
            return self._snapshot(connection, run_id)

    def finish_run(
        self,
        run_id: str,
        outcome: AnalysisRunOutcome,
        *,
        reason_code: str | None = None,
        lease_owner: str,
    ) -> AnalysisRunSnapshot:
        reason_code = _safe_reason_code(reason_code)
        now = _timestamp(self._clock())
        with self._write_transaction() as connection:
            current = self._require_run(connection, run_id)
            if current["lifecycle"] == AnalysisRunLifecycle.FINISHED.value:
                if current["outcome"] != outcome.value:
                    raise InvalidAnalysisRunTransitionError(
                        "A finished Analysis Run outcome cannot be replaced."
                    )
                if (
                    reason_code is not None
                    and current["reason_code"] != reason_code
                ):
                    raise InvalidAnalysisRunTransitionError(
                        "A finished Analysis Run reason cannot be replaced."
                    )
                return self._snapshot(connection, run_id)
            current = self._assert_current_lease(
                connection,
                run_id,
                lease_owner=lease_owner,
                allow_cancelling=True,
            )
            if current["lifecycle"] == AnalysisRunLifecycle.CANCELLING.value:
                outcome = AnalysisRunOutcome.CANCELLED
                reason_code = (
                    reason_code
                    if reason_code in {"cancelled", "operator_cancelled"}
                    else "cancelled"
                )
            if (
                reason_code is not None
                and current["reason_code"] is not None
                and current["reason_code"] != reason_code
            ):
                raise InvalidAnalysisRunTransitionError(
                    "An Analysis Run reason cannot be replaced."
                )
            active_call = connection.execute(
                """
                SELECT 1
                FROM analysis_provider_calls
                WHERE run_id = ?
                  AND state IN (
                      'reserved', 'dispatching', 'sent', 'response_recorded'
                  )
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            if active_call is not None:
                raise InvalidAnalysisRunTransitionError(
                    "An Analysis Run with an active provider call cannot finish."
                )
            persisted_reason_code = reason_code or current["reason_code"]
            connection.execute(
                """
                UPDATE analysis_runs
                SET lifecycle = 'finished',
                    outcome = ?,
                    reason_code = ?,
                    updated_at = ?,
                    finished_at = ?,
                    lease_owner = NULL,
                    lease_expires_at = NULL
                WHERE run_id = ?
                """,
                (outcome.value, persisted_reason_code, now, now, run_id),
            )
            return self._snapshot(connection, run_id)

    def reserve_provider_call(
        self,
        *,
        run_id: str,
        application_id: str,
        call_id: str,
        call_index: int,
        reservation_micros: int,
        authorization: AnalysisProviderAuthorizationMetadata,
        lease_owner: str,
    ) -> AnalysisProviderCallSnapshot | None:
        call_id = _require_identity("call_id", call_id)
        application_id = _require_identity("application_id", application_id)
        if type(call_index) is not int or call_index <= 0:
            raise ValueError("Provider authorization index must be a positive integer.")
        if type(reservation_micros) is not int or reservation_micros <= 0:
            raise ValueError("A provider call reservation must use positive integer USD micros.")
        if not isinstance(authorization, AnalysisProviderAuthorizationMetadata):
            raise TypeError("Provider authorization metadata has an invalid type.")
        now = _timestamp(self._clock())

        with self._write_transaction() as connection:
            self._assert_current_lease(
                connection,
                run_id,
                lease_owner=lease_owner,
                allow_cancelling=False,
            )
            candidate = connection.execute(
                """
                SELECT state
                FROM analysis_run_candidates
                WHERE run_id = ? AND application_id = ?
                """,
                (run_id, application_id),
            ).fetchone()
            if candidate is None:
                raise AnalysisRunStoreError(
                    "Provider work cannot be reserved for an Application outside the run."
                )
            transmission_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM analysis_provider_calls
                WHERE run_id = ?
                  AND application_id = ?
                  AND transmission_index IS NOT NULL
                """,
                (run_id, application_id),
            ).fetchone()[0]
            if transmission_count >= 3:
                raise ApplicationCallBudgetExhaustedError(
                    "An Application is limited to three provider transmissions."
                )
            spend = self._spend_totals(connection, run_id)
            if (
                spend["committed_spend_micros"] + reservation_micros
                > ANALYSIS_SPEND_CEILING_MICROS
            ):
                return None
            try:
                connection.execute(
                    """
                    INSERT INTO analysis_provider_calls (
                        call_id,
                        run_id,
                        application_id,
                        authorization_index,
                        state,
                        reservation_micros,
                        endpoint,
                        model,
                        approval_fingerprint,
                        request_fingerprint,
                        tokenizer_tokens,
                        utf8_bytes,
                        protocol_overhead_tokens,
                        input_cost_bound_tokens,
                        max_output_tokens,
                        cache_hit_input_micros_per_million_tokens,
                        cache_miss_input_micros_per_million_tokens,
                        output_micros_per_million_tokens,
                        created_at,
                        updated_at
                    ) VALUES (
                        ?, ?, ?, ?, 'reserved', ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?
                    )
                    """,
                    (
                        call_id,
                        run_id,
                        application_id,
                        call_index,
                        reservation_micros,
                        *(self._authorization_values(authorization)),
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise AnalysisRunStoreError(
                    "The provider call reservation identity is already in use."
                ) from exc
            return self._provider_call(connection, call_id)

    def list_provider_calls(
        self, run_id: str
    ) -> tuple[AnalysisProviderCallSnapshot, ...]:
        with self._read_connection() as connection:
            self._require_run(connection, run_id)
            return tuple(
                self._provider_call_from_row(row)
                for row in connection.execute(
                    """
                    SELECT *
                    FROM analysis_provider_calls
                    WHERE run_id = ?
                    ORDER BY application_id, authorization_index, call_id
                    """,
                    (run_id,),
                )
            )

    def transition_provider_call(
        self,
        call_id: str,
        state: AnalysisProviderCallState,
        *,
        verified_cost_micros: int | None = None,
        result_code: str | None = None,
        lease_owner: str,
    ) -> AnalysisProviderCallSnapshot:
        if state is AnalysisProviderCallState.DISPATCHING:
            if verified_cost_micros is not None:
                raise ValueError("Only a settled provider call records verified cost.")
            return self.begin_provider_dispatch(
                call_id, lease_owner=lease_owner
            )
        if state is AnalysisProviderCallState.SETTLED:
            if type(verified_cost_micros) is not int or verified_cost_micros < 0:
                raise ValueError(
                    "A settled provider call requires a non-negative integer-micro cost."
                )
        elif verified_cost_micros is not None:
            raise ValueError("Only a settled provider call records verified cost.")
        if result_code is not None:
            if state not in {
                AnalysisProviderCallState.SETTLED,
                AnalysisProviderCallState.INDETERMINATE,
            }:
                raise ValueError(
                    "Only a settled or indeterminate provider call records a result code."
                )
            if _safe_reason_code(result_code) is None:
                raise ValueError("Provider call result requires a safe result code.")
        now = _timestamp(self._clock())

        with self._write_transaction() as connection:
            current = self._provider_call(connection, call_id)
            self._assert_current_lease(
                connection,
                current.run_id,
                lease_owner=lease_owner,
                allow_cancelling=True,
            )
            if current.state is state:
                if (
                    current.verified_cost_micros != verified_cost_micros
                    or (
                        result_code is not None
                        and current.result_code != result_code
                    )
                ):
                    raise InvalidAnalysisRunTransitionError(
                        "Provider call settlement cannot be replaced."
                    )
                return current
            if state not in PROVIDER_CALL_TRANSITIONS[current.state]:
                raise InvalidAnalysisRunTransitionError(
                    f"A provider call cannot move from {current.state.value} to {state.value}."
                )
            if (
                verified_cost_micros is not None
                and verified_cost_micros > current.reservation_micros
            ):
                raise ValueError("Verified cost cannot exceed the durable reservation.")
            transmission_index = current.transmission_index
            if state is AnalysisProviderCallState.RELEASED:
                transmission_index = None
            connection.execute(
                """
                UPDATE analysis_provider_calls
                SET state = ?,
                    transmission_index = ?,
                    verified_cost_micros = ?,
                    result_code = CASE
                        WHEN ? IS NULL THEN result_code
                        ELSE ?
                    END,
                    updated_at = ?
                WHERE call_id = ?
                """,
                (
                    state.value,
                    transmission_index,
                    verified_cost_micros,
                    result_code,
                    result_code,
                    now,
                    call_id,
                ),
            )
            return self._provider_call(connection, call_id)

    def begin_provider_dispatch(
        self, call_id: str, *, lease_owner: str
    ) -> AnalysisProviderCallSnapshot:
        """Atomically revalidate authorization immediately before transmission."""
        now = _timestamp(self._clock())
        with self._write_transaction() as connection:
            current = self._provider_call(connection, call_id)
            self._assert_current_lease(
                connection,
                current.run_id,
                lease_owner=lease_owner,
                allow_cancelling=False,
            )
            if current.state is AnalysisProviderCallState.DISPATCHING:
                return current
            if current.state is not AnalysisProviderCallState.RESERVED:
                raise InvalidAnalysisRunTransitionError(
                    "Only a reserved provider authorization can begin dispatch."
                )
            candidate = connection.execute(
                """
                SELECT state
                FROM analysis_run_candidates
                WHERE run_id = ? AND application_id = ?
                """,
                (current.run_id, current.application_id),
            ).fetchone()
            if (
                candidate is None
                or candidate["state"] != AnalysisCandidateState.EVALUATING.value
            ):
                raise ProviderDispatchBlockedError(
                    "Provider dispatch requires the Application candidate to be evaluating."
                )
            in_flight = connection.execute(
                """
                SELECT call_id
                FROM analysis_provider_calls
                WHERE run_id = ?
                  AND call_id <> ?
                  AND state IN ('dispatching', 'sent', 'response_recorded')
                LIMIT 1
                """,
                (current.run_id, call_id),
            ).fetchone()
            if in_flight is not None:
                raise ProviderDispatchBlockedError(
                    "Another provider call is already in flight for this Analysis Run."
                )
            transmission_index = self._next_transmission_index(
                connection,
                current.run_id,
                current.application_id,
            )
            if transmission_index is None:
                raise ApplicationCallBudgetExhaustedError(
                    "An Application is limited to three provider transmissions."
                )
            connection.execute(
                """
                UPDATE analysis_provider_calls
                SET state = 'dispatching',
                    transmission_index = ?,
                    updated_at = ?
                WHERE call_id = ? AND state = 'reserved'
                """,
                (transmission_index, now, call_id),
            )
            return self._provider_call(connection, call_id)

    def release_provider_call(
        self, call_id: str, *, lease_owner: str
    ) -> AnalysisProviderCallSnapshot:
        """Release cost only when the caller proves transmission never happened."""
        now = _timestamp(self._clock())
        with self._write_transaction() as connection:
            current = self._provider_call(connection, call_id)
            self._assert_current_lease(
                connection,
                current.run_id,
                lease_owner=lease_owner,
                allow_cancelling=True,
            )
            if current.state is AnalysisProviderCallState.RELEASED:
                return current
            if current.state not in {
                AnalysisProviderCallState.RESERVED,
                AnalysisProviderCallState.DISPATCHING,
            }:
                raise InvalidAnalysisRunTransitionError(
                    "A sent provider call cannot release its durable reservation."
                )
            connection.execute(
                """
                UPDATE analysis_provider_calls
                SET state = 'released', transmission_index = NULL, updated_at = ?
                WHERE call_id = ?
                """,
                (now, call_id),
            )
            return self._provider_call(connection, call_id)

    def settle_provider_call(
        self,
        call_id: str,
        *,
        verified_cost_micros: int,
        result_code: str | None = None,
        lease_owner: str,
    ) -> AnalysisProviderCallSnapshot:
        return self.transition_provider_call(
            call_id,
            AnalysisProviderCallState.SETTLED,
            verified_cost_micros=verified_cost_micros,
            result_code=result_code,
            lease_owner=lease_owner,
        )

    def record_provider_call_response(
        self,
        call_id: str,
        metadata: AnalysisProviderSettlementMetadata,
        *,
        lease_owner: str,
    ) -> AnalysisProviderCallSnapshot:
        if not isinstance(metadata, AnalysisProviderSettlementMetadata):
            raise TypeError("Provider settlement metadata has an invalid type.")
        now = _timestamp(self._clock())
        with self._write_transaction() as connection:
            current = self._provider_call(connection, call_id)
            self._assert_current_lease(
                connection,
                current.run_id,
                lease_owner=lease_owner,
                allow_cancelling=True,
            )
            if current.state is AnalysisProviderCallState.RESPONSE_RECORDED:
                if self._settlement_values_from_snapshot(current) != (
                    metadata.provider_request_id,
                    metadata.input_tokens,
                    metadata.output_tokens,
                    metadata.cache_hit_input_tokens,
                    metadata.cache_miss_input_tokens,
                    metadata.total_tokens,
                    metadata.reasoning_output_tokens,
                    metadata.finish_reason,
                    metadata.result_code,
                ):
                    raise InvalidAnalysisRunTransitionError(
                        "Provider settlement metadata cannot be replaced."
                    )
                return current
            if current.state not in {
                AnalysisProviderCallState.DISPATCHING,
                AnalysisProviderCallState.SENT,
            }:
                raise InvalidAnalysisRunTransitionError(
                    "Only a transmitted provider call can record response metadata."
                )
            connection.execute(
                """
                UPDATE analysis_provider_calls
                SET state = 'response_recorded',
                    provider_request_id = ?,
                    input_tokens = ?,
                    output_tokens = ?,
                    cache_hit_input_tokens = ?,
                    cache_miss_input_tokens = ?,
                    total_tokens = ?,
                    reasoning_output_tokens = ?,
                    finish_reason = ?,
                    result_code = ?,
                    updated_at = ?
                WHERE call_id = ?
                """,
                (
                    metadata.provider_request_id,
                    metadata.input_tokens,
                    metadata.output_tokens,
                    metadata.cache_hit_input_tokens,
                    metadata.cache_miss_input_tokens,
                    metadata.total_tokens,
                    metadata.reasoning_output_tokens,
                    metadata.finish_reason,
                    metadata.result_code,
                    now,
                    call_id,
                ),
            )
            return self._provider_call(connection, call_id)

    def quarantine_commit_unknown(
        self, run_id: str, application_id: str, *, lease_owner: str
    ) -> None:
        """Exclude an Application whose remote mutation has no final result."""
        application_id = _require_identity("application_id", application_id)
        now = _timestamp(self._clock())
        with self._write_transaction() as connection:
            self._assert_current_lease(
                connection,
                run_id,
                lease_owner=lease_owner,
                allow_cancelling=True,
            )
            candidate = connection.execute(
                """
                SELECT 1 FROM analysis_run_candidates
                WHERE run_id = ? AND application_id = ?
                """,
                (run_id, application_id),
            ).fetchone()
            if candidate is None:
                raise AnalysisRunStoreError(
                    "Commit quarantine requires an Analysis Run candidate."
                )
            connection.execute(
                """
                INSERT INTO analysis_commit_quarantine (
                    application_id, run_id, created_at
                ) VALUES (?, ?, ?)
                ON CONFLICT(application_id) DO NOTHING
                """,
                (application_id, run_id, now),
            )

    def clear_commit_quarantine(self, application_id: str) -> None:
        application_id = _require_identity("application_id", application_id)
        with self._write_transaction() as connection:
            connection.execute(
                "DELETE FROM analysis_commit_quarantine WHERE application_id = ?",
                (application_id,),
            )

    def list_commit_quarantines(self) -> tuple[str, ...]:
        with self._read_connection() as connection:
            return tuple(
                row["application_id"]
                for row in connection.execute(
                    """
                    SELECT application_id
                    FROM analysis_commit_quarantine
                    ORDER BY created_at, application_id
                    """
                )
            )

    def reconcile_interrupted_provider_calls(
        self, run_id: str, *, lease_owner: str
    ) -> tuple[AnalysisProviderCallSnapshot, ...]:
        """Conservatively classify call state left by an interrupted process."""
        now = _timestamp(self._clock())
        with self._write_transaction() as connection:
            self._assert_current_lease(
                connection,
                run_id,
                lease_owner=lease_owner,
                allow_cancelling=True,
            )
            connection.execute(
                """
                UPDATE analysis_provider_calls
                SET state = CASE
                        WHEN state = 'reserved' THEN 'released'
                        WHEN state IN ('dispatching', 'sent') THEN 'indeterminate'
                        ELSE state
                    END,
                    transmission_index = CASE
                        WHEN state = 'reserved' THEN NULL
                        ELSE transmission_index
                    END,
                    updated_at = CASE
                        WHEN state IN ('reserved', 'dispatching', 'sent') THEN ?
                        ELSE updated_at
                    END
                WHERE run_id = ?
                  AND state IN ('reserved', 'dispatching', 'sent')
                """,
                (now, run_id),
            )
            return tuple(
                self._provider_call_from_row(row)
                for row in connection.execute(
                    """
                    SELECT *
                    FROM analysis_provider_calls
                    WHERE run_id = ?
                    ORDER BY application_id, authorization_index, call_id
                    """,
                    (run_id,),
                )
            )

    def _require_run(
        self, connection: sqlite3.Connection, run_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM analysis_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            raise AnalysisRunNotFoundError("The Analysis Run does not exist.")
        return row

    def _assert_current_lease(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        *,
        lease_owner: str,
        allow_cancelling: bool,
    ) -> sqlite3.Row:
        lease_owner = _require_identity("lease_owner", lease_owner)
        run = self._require_run(connection, run_id)
        allowed_lifecycles = {AnalysisRunLifecycle.RUNNING.value}
        if allow_cancelling:
            allowed_lifecycles.add(AnalysisRunLifecycle.CANCELLING.value)
        if run["lifecycle"] not in allowed_lifecycles:
            raise AnalysisRunLeaseError(
                "The Analysis Run is outside its leased work lifecycle."
            )
        if run["lease_owner"] != lease_owner:
            raise AnalysisRunLeaseError(
                "The Analysis Run lease is owned by another worker."
            )
        now = _timestamp(self._clock())
        if run["lease_expires_at"] is None or run["lease_expires_at"] <= now:
            raise AnalysisRunLeaseError("The Analysis Run lease has expired.")
        return run

    def _refresh_progress(
        self, connection: sqlite3.Connection, run_id: str, updated_at: str
    ) -> None:
        counts = connection.execute(
            """
            SELECT
                SUM(CASE WHEN state IN ('analyzed', 'repaired') THEN 1 ELSE 0 END)
                    AS completion_count,
                SUM(CASE WHEN state = 'repaired' THEN 1 ELSE 0 END)
                    AS repaired_count,
                SUM(CASE WHEN state IN (
                    'analyzed', 'repaired', 'skipped', 'failed', 'indeterminate'
                ) THEN 1 ELSE 0 END) AS evaluated_count,
                SUM(CASE WHEN state = 'skipped' THEN 1 ELSE 0 END) AS skipped_count,
                SUM(CASE WHEN state = 'failed' THEN 1 ELSE 0 END) AS failed_count,
                SUM(CASE WHEN state = 'indeterminate' THEN 1 ELSE 0 END)
                    AS indeterminate_count
            FROM analysis_run_candidates
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        connection.execute(
            """
            UPDATE analysis_runs
            SET completion_count = ?,
                repaired_count = ?,
                evaluated_count = ?,
                skipped_count = ?,
                failed_count = ?,
                indeterminate_count = ?,
                updated_at = ?
            WHERE run_id = ?
            """,
            (
                counts["completion_count"] or 0,
                counts["repaired_count"] or 0,
                counts["evaluated_count"] or 0,
                counts["skipped_count"] or 0,
                counts["failed_count"] or 0,
                counts["indeterminate_count"] or 0,
                updated_at,
                run_id,
            ),
        )

    def _snapshot(
        self, connection: sqlite3.Connection, run_id: str
    ) -> AnalysisRunSnapshot:
        row = self._require_run(connection, run_id)
        spend = self._spend_totals(connection, run_id)
        candidates = tuple(
            AnalysisCandidateSnapshot(
                application_id=candidate["application_id"],
                ordinal=candidate["ordinal"],
                state=AnalysisCandidateState(candidate["state"]),
                reason_code=candidate["reason_code"],
                started_at=_optional_datetime(candidate["started_at"]),
                completed_at=_optional_datetime(candidate["completed_at"]),
            )
            for candidate in connection.execute(
                """
                SELECT application_id, ordinal, state, reason_code,
                       started_at, completed_at
                FROM analysis_run_candidates
                WHERE run_id = ?
                ORDER BY ordinal
                """,
                (run_id,),
            )
        )
        return AnalysisRunSnapshot(
            run_id=row["run_id"],
            lifecycle=AnalysisRunLifecycle(row["lifecycle"]),
            outcome=(
                None
                if row["outcome"] is None
                else AnalysisRunOutcome(row["outcome"])
            ),
            reason_code=row["reason_code"],
            target=row["target"],
            attempt_budget=row["attempt_budget"],
            candidate_set_truncated=bool(row["candidate_set_truncated"]),
            created_at=_datetime(row["created_at"]),
            updated_at=_datetime(row["updated_at"]),
            started_at=_optional_datetime(row["started_at"]),
            finished_at=_optional_datetime(row["finished_at"]),
            lease_owner=row["lease_owner"],
            lease_expires_at=_optional_datetime(row["lease_expires_at"]),
            completion_count=row["completion_count"],
            repaired_count=row["repaired_count"],
            evaluated_count=row["evaluated_count"],
            skipped_count=row["skipped_count"],
            failed_count=row["failed_count"],
            indeterminate_count=row["indeterminate_count"],
            spend_ceiling_micros=ANALYSIS_SPEND_CEILING_MICROS,
            committed_spend_micros=spend["committed_spend_micros"],
            verified_cost_micros=spend["verified_cost_micros"],
            active_reservation_micros=spend["active_reservation_micros"],
            indeterminate_reservation_micros=spend[
                "indeterminate_reservation_micros"
            ],
            remaining_authorized_micros=(
                ANALYSIS_SPEND_CEILING_MICROS - spend["committed_spend_micros"]
            ),
            candidates=candidates,
        )

    def _candidate_from_row(self, row: sqlite3.Row) -> AnalysisCandidateSnapshot:
        return AnalysisCandidateSnapshot(
            application_id=row["application_id"],
            ordinal=row["ordinal"],
            state=AnalysisCandidateState(row["state"]),
            reason_code=row["reason_code"],
            started_at=_optional_datetime(row["started_at"]),
            completed_at=_optional_datetime(row["completed_at"]),
        )

    def _provider_call(
        self, connection: sqlite3.Connection, call_id: str
    ) -> AnalysisProviderCallSnapshot:
        row = connection.execute(
            "SELECT * FROM analysis_provider_calls WHERE call_id = ?", (call_id,)
        ).fetchone()
        if row is None:
            raise AnalysisRunStoreError("The provider call does not exist.")
        return self._provider_call_from_row(row)

    def _provider_call_from_row(
        self, row: sqlite3.Row
    ) -> AnalysisProviderCallSnapshot:
        return AnalysisProviderCallSnapshot(
            call_id=row["call_id"],
            run_id=row["run_id"],
            application_id=row["application_id"],
            authorization_index=row["authorization_index"],
            transmission_index=row["transmission_index"],
            state=AnalysisProviderCallState(row["state"]),
            reservation_micros=row["reservation_micros"],
            verified_cost_micros=row["verified_cost_micros"],
            created_at=_datetime(row["created_at"]),
            updated_at=_datetime(row["updated_at"]),
            endpoint=row["endpoint"],
            model=row["model"],
            approval_fingerprint=row["approval_fingerprint"],
            request_fingerprint=row["request_fingerprint"],
            tokenizer_tokens=row["tokenizer_tokens"],
            utf8_bytes=row["utf8_bytes"],
            protocol_overhead_tokens=row["protocol_overhead_tokens"],
            input_cost_bound_tokens=row["input_cost_bound_tokens"],
            max_output_tokens=row["max_output_tokens"],
            cache_hit_input_micros_per_million_tokens=row[
                "cache_hit_input_micros_per_million_tokens"
            ],
            cache_miss_input_micros_per_million_tokens=row[
                "cache_miss_input_micros_per_million_tokens"
            ],
            output_micros_per_million_tokens=row[
                "output_micros_per_million_tokens"
            ],
            provider_request_id=row["provider_request_id"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            cache_hit_input_tokens=row["cache_hit_input_tokens"],
            cache_miss_input_tokens=row["cache_miss_input_tokens"],
            total_tokens=row["total_tokens"],
            reasoning_output_tokens=row["reasoning_output_tokens"],
            finish_reason=row["finish_reason"],
            result_code=row["result_code"],
        )

    def _authorization_values(
        self, metadata: AnalysisProviderAuthorizationMetadata | None
    ) -> tuple[object, ...]:
        if metadata is None:
            return (None,) * 12
        return (
            metadata.endpoint,
            metadata.model,
            metadata.approval_fingerprint,
            metadata.request_fingerprint,
            metadata.tokenizer_tokens,
            metadata.utf8_bytes,
            metadata.protocol_overhead_tokens,
            metadata.input_cost_bound_tokens,
            metadata.max_output_tokens,
            metadata.cache_hit_input_micros_per_million_tokens,
            metadata.cache_miss_input_micros_per_million_tokens,
            metadata.output_micros_per_million_tokens,
        )

    def _settlement_values_from_snapshot(
        self, snapshot: AnalysisProviderCallSnapshot
    ) -> tuple[object, ...]:
        return (
            snapshot.provider_request_id,
            snapshot.input_tokens,
            snapshot.output_tokens,
            snapshot.cache_hit_input_tokens,
            snapshot.cache_miss_input_tokens,
            snapshot.total_tokens,
            snapshot.reasoning_output_tokens,
            snapshot.finish_reason,
            snapshot.result_code,
        )

    def _next_transmission_index(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        application_id: str,
    ) -> int | None:
        used = {
            row["transmission_index"]
            for row in connection.execute(
                """
                SELECT transmission_index
                FROM analysis_provider_calls
                WHERE run_id = ?
                  AND application_id = ?
                  AND transmission_index IS NOT NULL
                """,
                (run_id, application_id),
            )
        }
        return next((index for index in range(1, 4) if index not in used), None)

    def _spend_totals(
        self, connection: sqlite3.Connection, run_id: str
    ) -> dict[str, int]:
        row = connection.execute(
            """
            SELECT
                COALESCE(SUM(
                    CASE
                        WHEN state = 'settled' THEN verified_cost_micros
                        WHEN state IN (
                            'reserved', 'dispatching', 'sent', 'response_recorded',
                            'indeterminate'
                        ) THEN reservation_micros
                        ELSE 0
                    END
                ), 0) AS committed_spend_micros,
                COALESCE(SUM(
                    CASE WHEN state = 'settled' THEN verified_cost_micros ELSE 0 END
                ), 0) AS verified_cost_micros,
                COALESCE(SUM(
                    CASE
                        WHEN state IN ('reserved', 'dispatching', 'sent', 'response_recorded')
                        THEN reservation_micros
                        ELSE 0
                    END
                ), 0) AS active_reservation_micros,
                COALESCE(SUM(
                    CASE WHEN state = 'indeterminate' THEN reservation_micros ELSE 0 END
                ), 0) AS indeterminate_reservation_micros
            FROM analysis_provider_calls
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        return {
            "committed_spend_micros": row["committed_spend_micros"],
            "verified_cost_micros": row["verified_cost_micros"],
            "active_reservation_micros": row["active_reservation_micros"],
            "indeterminate_reservation_micros": row[
                "indeterminate_reservation_micros"
            ],
        }


class UnavailableAnalysisRunStore:
    """Fail-closed store used when durable transactional coordination cannot open."""

    def __init__(self, error: str = "Analysis Run coordination is unavailable."):
        self._error = error

    @property
    def available(self) -> bool:
        return False

    @property
    def transactional(self) -> bool:
        return False

    @property
    def error(self) -> str:
        return self._error

    def reserve_provider_call(self, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def create_run(self, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def start_run(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def record_candidate_result(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def finish_run(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def transition_provider_call(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def get_run(self, _run_id: str) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def get_by_idempotency_key(self, _idempotency_key: str) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def get_active_run(self) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def list_provider_calls(self, _run_id: str) -> tuple[()]:
        raise AnalysisRunStoreUnavailableError(self._error)

    def claim_recoverable_run(self, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def renew_lease(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def protect_remote_commit(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def relinquish_lease(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def claim_next_candidate(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def request_cancellation(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def record_run_reason(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def list_recoverable_runs(self) -> tuple[()]:
        raise AnalysisRunStoreUnavailableError(self._error)

    def reconcile_interrupted_provider_calls(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def release_provider_call(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def settle_provider_call(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def begin_provider_dispatch(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def record_provider_call_response(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def quarantine_commit_unknown(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def clear_commit_quarantine(self, *_args, **_kwargs) -> None:
        raise AnalysisRunStoreUnavailableError(self._error)

    def list_commit_quarantines(self) -> tuple[()]:
        raise AnalysisRunStoreUnavailableError(self._error)


def open_analysis_run_store(
    path: Path,
    *,
    clock: Callable[[], datetime] | None = None,
) -> SqliteAnalysisRunStore | UnavailableAnalysisRunStore:
    try:
        return SqliteAnalysisRunStore(path, clock=clock)
    except (OSError, sqlite3.Error, AnalysisRunStoreError):
        return UnavailableAnalysisRunStore()


def _require_identity(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 255:
        raise ValueError(f"{name} must be a non-empty identity of at most 255 characters.")
    if "\n" in value or "\r" in value:
        raise ValueError(f"{name} cannot contain line breaks.")
    return value


def _execute_sql_script(
    connection: sqlite3.Connection, script: str
) -> None:
    """Execute a SQL script without sqlite3.executescript's implicit commit."""
    statement = ""
    for line in script.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            connection.execute(statement)
            statement = ""
    if statement.strip():
        raise AnalysisRunStoreError("The Analysis Run Store migration is invalid.")


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def _recover_interrupted_provider_call_migration(
    connection: sqlite3.Connection,
) -> None:
    """Preserve every paid-call fact left by the old autocommit migration."""
    intermediate = "analysis_provider_calls_v2"
    current = "analysis_provider_calls"
    if not _table_exists(connection, intermediate):
        return
    if _table_exists(connection, current):
        current_count = connection.execute(
            f"SELECT COUNT(*) FROM {current}"
        ).fetchone()[0]
        if current_count == 0:
            connection.execute(f"DROP TABLE {current}")
            connection.execute(
                f"ALTER TABLE {intermediate} RENAME TO {current}"
            )
            return
        _merge_interrupted_provider_call_tables(
            connection,
            current=current,
            intermediate=intermediate,
        )
        return
    connection.execute(f"ALTER TABLE {intermediate} RENAME TO {current}")


def _merge_interrupted_provider_call_tables(
    connection: sqlite3.Connection,
    *,
    current: str,
    intermediate: str,
) -> None:
    current_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({current})")
    }
    intermediate_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({intermediate})")
    }
    required_current = {
        "call_id",
        "run_id",
        "application_id",
        "authorization_index",
        "transmission_index",
        "state",
        "reservation_micros",
        "verified_cost_micros",
        "created_at",
        "updated_at",
    }
    if not required_current <= current_columns:
        raise AnalysisRunStoreError(
            "Interrupted provider-call migration requires operator inspection."
        )
    if "call_index" in intermediate_columns:
        authorization_index = "source.call_index"
        transmission_index = (
            "CASE WHEN source.state IN ('reserved', 'released') "
            "THEN NULL ELSE source.call_index END"
        )
    elif {
        "authorization_index",
        "transmission_index",
    } <= intermediate_columns:
        authorization_index = "source.authorization_index"
        transmission_index = "source.transmission_index"
    else:
        raise AnalysisRunStoreError(
            "Interrupted provider-call migration requires operator inspection."
        )

    conflicting_identity = connection.execute(
        f"""
        SELECT 1
        FROM {intermediate} AS source
        JOIN {current} AS destination USING (call_id)
        WHERE destination.run_id IS NOT source.run_id
           OR destination.application_id IS NOT source.application_id
           OR destination.authorization_index IS NOT {authorization_index}
           OR destination.reservation_micros IS NOT source.reservation_micros
        LIMIT 1
        """
    ).fetchone()
    if conflicting_identity is not None:
        raise AnalysisRunStoreError(
            "Interrupted provider-call migration contains conflicting paid-call facts."
        )

    connection.execute(
        f"""
        INSERT INTO {current} (
            call_id,
            run_id,
            application_id,
            authorization_index,
            transmission_index,
            state,
            reservation_micros,
            verified_cost_micros,
            created_at,
            updated_at
        )
        SELECT
            source.call_id,
            source.run_id,
            source.application_id,
            {authorization_index},
            {transmission_index},
            source.state,
            source.reservation_micros,
            source.verified_cost_micros,
            source.created_at,
            source.updated_at
        FROM {intermediate} AS source
        WHERE NOT EXISTS (
            SELECT 1 FROM {current} AS destination
            WHERE destination.call_id = source.call_id
        )
        """
    )
    connection.execute(f"DROP TABLE {intermediate}")


def _idempotency_digest(value: str) -> str:
    identity = _require_identity("idempotency_key", value)
    return "sha256:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _is_idempotency_digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(
        r"sha256:[0-9a-f]{64}", value
    ) is not None


def _safe_reason_code(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value) is None:
        raise ValueError(
            "Analysis coordination metadata requires a stable safe reason code."
        )
    return value


def _safe_provider_endpoint(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("Provider endpoint must be a safe HTTPS URL.")
    parts = urlsplit(value)
    if (
        parts.scheme != "https"
        or not parts.netloc
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or "\n" in value
        or "\r" in value
    ):
        raise ValueError("Provider endpoint must be a safe HTTPS URL.")
    return value


def _safe_provider_identity(name: str, value: str) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}", value) is None
    ):
        raise ValueError(f"Provider metadata requires a safe {name} identity.")
    return value


def _nonnegative_integer(name: str, value: int) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer.")
    return value


def _positive_integer(name: str, value: int) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Analysis Run timestamps must include a timezone.")
    return value.astimezone(timezone.utc).isoformat()


def _future_timestamp(value: datetime, *, after: datetime) -> str:
    normalized_value = _datetime(_timestamp(value))
    normalized_after = _datetime(_timestamp(after))
    if normalized_value <= normalized_after:
        raise ValueError("An Analysis Run lease must expire in the future.")
    return normalized_value.isoformat()


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _optional_datetime(value: str | None) -> datetime | None:
    return None if value is None else _datetime(value)
