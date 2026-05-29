from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.base import UnsupportedPublishModeError
from backend.app.adapters.registry import get_adapter
from backend.app.models.content import PreviewRecord
from backend.app.models.platform import PublishMode, PublishTaskRecord, PublishTaskStatus
from backend.app.schemas.content import PublishTaskCreateRequest, PublishTaskResponse


class PublishService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_task(self, request: PublishTaskCreateRequest) -> PublishTaskRecord | None:
        if request.mode != PublishMode.SIMULATE:
            raise UnsupportedPublishModeError(
                "Only simulate mode is supported in the MVP backend."
            )

        preview = await self.session.get(PreviewRecord, request.preview_id)
        if preview is None:
            return None

        platforms = request.platforms or list(preview.drafts.keys())
        results: dict[str, dict] = {}
        status = PublishTaskStatus.SUCCEEDED
        error_message: str | None = None

        for platform in platforms:
            draft = preview.drafts.get(platform)
            if draft is None:
                status = PublishTaskStatus.FAILED
                results[platform] = {
                    "platform": platform,
                    "status": "failed",
                    "message": "No draft exists for this platform in the preview.",
                }
                continue

            try:
                adapter = get_adapter(platform)
                results[platform] = await adapter.publish(draft, mode=request.mode)
            except Exception as exc:  # keep per-platform failure visible in MVP reports
                status = PublishTaskStatus.FAILED
                results[platform] = {
                    "platform": platform,
                    "status": "failed",
                    "message": str(exc),
                }
                error_message = str(exc)

        task = PublishTaskRecord(
            preview_id=preview.id,
            mode=request.mode,
            status=status,
            platforms=platforms,
            results=results,
            error_message=error_message,
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get_task(self, task_id: str) -> PublishTaskRecord | None:
        return await self.session.get(PublishTaskRecord, task_id)

    @staticmethod
    def to_response(record: PublishTaskRecord) -> PublishTaskResponse:
        return PublishTaskResponse(
            task_id=record.id,
            preview_id=record.preview_id,
            mode=record.mode,
            status=record.status,
            platforms=record.platforms,
            results=record.results,
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
