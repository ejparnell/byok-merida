from .ports import ApplicationAnalysisStore


class ApplicationAnalysis:
    def __init__(self, store: ApplicationAnalysisStore):
        self._store = store

    async def get_queue(self, limit: int, cursor: str | None) -> dict:
        return await self._store.analysis_queue(limit, cursor)

    async def run_batch(self, limit: int) -> dict:
        return await self._store.run_analysis(limit)
