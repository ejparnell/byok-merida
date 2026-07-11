from typing import Protocol

from .schemas import ConfirmedApplicationDraft


class CaptureStore(Protocol):
    async def confirm_capture(self, draft: ConfirmedApplicationDraft) -> dict: ...


class ApplicationAnalysisStore(Protocol):
    async def analysis_queue(self, limit: int, cursor: str | None) -> dict: ...
    async def run_analysis(self, limit: int) -> dict: ...
