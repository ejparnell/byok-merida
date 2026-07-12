import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


class OperationConflict(RuntimeError):
    def __init__(self, message: str, *, active_run_id: str | None = None):
        super().__init__(message)
        self.active_run_id = active_run_id


@dataclass(frozen=True)
class ActiveRun:
    run_id: str
    key: str
    started_at: datetime


class ExecutionCoordinator:
    def __init__(self):
        self._guard = asyncio.Lock()
        self._active: dict[str, ActiveRun] = {}

    @asynccontextmanager
    async def exclusive(
        self,
        key: str,
        conflict_message: str,
        *,
        conflict_keys: tuple[str, ...] = (),
        conflict_prefixes: tuple[str, ...] = (),
    ):
        async with self._guard:
            conflicts = key in self._active or any(
                conflict_key in self._active for conflict_key in conflict_keys
            )
            conflicts = conflicts or any(
                active_key.startswith(prefix)
                for active_key in self._active
                for prefix in conflict_prefixes
            )
            if conflicts:
                conflicting_run = self._active.get(key)
                if conflicting_run is None:
                    conflicting_run = next(
                        (
                            run
                            for active_key, run in self._active.items()
                            if active_key in conflict_keys
                            or any(
                                active_key.startswith(prefix)
                                for prefix in conflict_prefixes
                            )
                        ),
                        None,
                    )
                raise OperationConflict(
                    conflict_message,
                    active_run_id=conflicting_run.run_id
                    if conflicting_run
                    else None,
                )
            run = ActiveRun(
                run_id=uuid4().hex,
                key=key,
                started_at=datetime.now(timezone.utc),
            )
            self._active[key] = run
        try:
            yield run
        finally:
            async with self._guard:
                self._active.pop(key, None)
