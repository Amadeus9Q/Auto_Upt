from __future__ import annotations

import asyncio

from backend.app.db.session import AsyncSessionLocal, close_db
from backend.app.services.publish_service import PublishService
from backend.app.tasks.celery_app import celery_app


@celery_app.task(name="backend.app.tasks.publish.execute_publish_task")
def execute_publish_task(task_id: str) -> dict[str, str | None]:
    return asyncio.run(_execute_publish_task_with_connection_cleanup(task_id))


async def _execute_publish_task_with_connection_cleanup(task_id: str) -> dict[str, str | None]:
    await close_db()
    try:
        return await _execute_publish_task(task_id)
    finally:
        await close_db()


async def _execute_publish_task(task_id: str) -> dict[str, str | None]:
    failure_message: str | None = None
    record_id: str | None = None
    record_status: str | None = None

    async with AsyncSessionLocal() as session:
        service = PublishService(session)
        try:
            record = await service.execute_real_task(task_id)
        except Exception as exc:
            try:
                await session.rollback()
            except Exception:
                pass
            failure_message = f"Publish worker failed unexpectedly: {exc}"
        else:
            if record is None:
                return {"task_id": task_id, "status": None}
            record_id = record.id
            record_status = record.status

    if failure_message is not None:
        await close_db()
        async with AsyncSessionLocal() as session:
            record = await PublishService(session).mark_task_failed(task_id, failure_message)
            if record is None:
                raise RuntimeError(failure_message)
            record_id = record.id
            record_status = record.status

    return {"task_id": record_id, "status": record_status}
