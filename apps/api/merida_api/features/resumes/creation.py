from .ports import ResumeCreationStore


class ResumeCreation:
    def __init__(self, store: ResumeCreationStore):
        self._store = store

    async def get_queue(self, limit: int, cursor: str | None) -> dict:
        return await self._store.resume_queue(limit, cursor)

    async def create(self, application_id: str) -> dict:
        return await self._store.create_resume(application_id)

    def pdf_path(self, resume_id: str):
        return self._store.pdf_path(resume_id)
