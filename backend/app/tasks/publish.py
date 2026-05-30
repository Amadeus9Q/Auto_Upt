from __future__ import annotations

import asyncio

from backend.app.db.session import AsyncSessionLocal
from backend.app.services.publish_service import PublishService
from backend.app.tasks.celery_app import celery_app


@celery_app.task(name="backend.app.tasks.publish.execute_publish_task")
def execute_publish_task(task_id: str) -> dict[str, str | None]:
    return asyncio.run(_execute_publish_task(task_id))


async def _execute_publish_task(task_id: str) -> dict[str, str | None]:
    async with AsyncSessionLocal() as session:
        service = PublishService(session)
        try:
            record = await service.execute_real_task(task_id)
        except Exception as exc:
            await session.rollback()
            message = f"Publish worker failed unexpectedly: {exc}"
            record = await service.mark_task_failed(task_id, message)
            if record is None:
                raise
        if record is None:
            return {"task_id": task_id, "status": None}
        return {"task_id": record.id, "status": record.status}
