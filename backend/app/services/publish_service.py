from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.base import UnsupportedPublishModeError
from backend.app.adapters.clients import (
    BilibiliWebClient,
    LocalAsset,
    PlatformClientError,
    WechatOfficialAccountClient,
)
from backend.app.adapters.registry import get_adapter
from backend.app.models.account import ConnectedAccountRecord
from backend.app.models.asset import ContentAssetRecord
from backend.app.models.content import PreviewRecord
from backend.app.models.platform import PublishMode, PublishTaskRecord, PublishTaskStatus
from backend.app.models.publication import PublicationRecord
from backend.app.schemas.content import PublishTaskCreateRequest, PublishTaskResponse
from backend.app.schemas.publication import PublicationDeleteResponse, PublicationResponse
from backend.app.services.account_service import AccountService


REAL_PUBLISH_PLATFORMS = {"wechat", "bilibili"}


class PublishService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_task(self, request: PublishTaskCreateRequest) -> PublishTaskRecord | None:
        preview = await self.session.get(PreviewRecord, request.preview_id)
        if preview is None:
            return None

        platforms = request.platforms or list(preview.drafts.keys())
        if request.mode == PublishMode.SIMULATE:
            return await self._create_simulation_task(preview, request, platforms)

        self._validate_real_publish_request(request, platforms)
        task = PublishTaskRecord(
            preview_id=preview.id,
            mode=request.mode,
            status=PublishTaskStatus.PENDING,
            platforms=platforms,
            account_ids=dict(request.account_ids),
            asset_ids={platform: ids for platform, ids in request.asset_ids.items()},
            platform_options={platform: options for platform, options in request.platform_options.items()},
            results={
                platform: {
                    "platform": platform,
                    "status": "pending",
                    "message": "Real publish task queued.",
                }
                for platform in platforms
            },
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)

        if not self._enqueue_real_publish(task.id):
            task.status = PublishTaskStatus.FAILED
            task.error_message = "Celery is not available. Install dependencies and start the worker."
            task.results = {
                platform: {
                    "platform": platform,
                    "status": "failed",
                    "message": task.error_message,
                    "retryable": True,
                    "next_action": "请安装依赖并启动 Celery worker 后重试。",
                }
                for platform in platforms
            }
            await self.session.commit()
            await self.session.refresh(task)

        return task

    async def execute_real_task(self, task_id: str) -> PublishTaskRecord | None:
        task = await self.get_task(task_id)
        if task is None:
            return None

        preview = await self.session.get(PreviewRecord, task.preview_id)
        if preview is None:
            task.status = PublishTaskStatus.FAILED
            task.error_message = "Preview not found."
            await self.session.commit()
            return task

        task.status = PublishTaskStatus.RUNNING
        await self.session.commit()
        results: dict[str, dict[str, Any]] = {}
        failed = False

        for platform in task.platforms:
            draft = preview.drafts.get(platform)
            if draft is None:
                failed = True
                results[platform] = {
                    "platform": platform,
                    "status": "failed",
                    "message": "No draft exists for this platform in the preview.",
                    "retryable": False,
                    "next_action": "请重新生成包含该平台的预览。",
                }
                continue

            publication = PublicationRecord(
                task_id=task.id,
                preview_id=preview.id,
                account_id=task.account_ids.get(platform),
                platform=platform,
                mode=task.mode,
                status="running",
                request_payload={
                    "draft": draft,
                    "asset_ids": task.asset_ids.get(platform, []),
                    "platform_options": task.platform_options.get(platform, {}),
                },
            )
            self.session.add(publication)
            await self.session.commit()
            await self.session.refresh(publication)

            try:
                context = await self._build_account_context(task, platform)
                adapter = get_adapter(platform)
                publish_result = await adapter.publish(draft, account=context, mode=task.mode)
                publication.status = publish_result.get("status", "succeeded")
                publication.external_id = publish_result.get("external_id")
                publication.external_url = publish_result.get("external_url")
                publication.external_status = publish_result.get("external_status")
                publication.response_payload = publish_result
                results[platform] = {
                    **publish_result,
                    "publication_id": publication.id,
                }
            except PlatformClientError as exc:
                failed = True
                error_result = exc.to_result(platform)
                publication.status = "failed"
                publication.error_message = str(exc)
                publication.response_payload = error_result
                results[platform] = {
                    **error_result,
                    "publication_id": publication.id,
                }
            except Exception as exc:
                failed = True
                publication.status = "failed"
                publication.error_message = str(exc)
                results[platform] = {
                    "platform": platform,
                    "status": "failed",
                    "message": str(exc),
                    "retryable": False,
                    "next_action": "请查看后端日志并确认平台参数。",
                    "publication_id": publication.id,
                }

            await self.session.commit()

        task.status = PublishTaskStatus.FAILED if failed else PublishTaskStatus.SUCCEEDED
        task.results = results
        task.error_message = "One or more platforms failed." if failed else None
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def refresh_task(self, task_id: str) -> PublishTaskRecord | None:
        task = await self.get_task(task_id)
        if task is None:
            return None

        publications = await self._list_publications_by_task(task.id)
        results = dict(task.results or {})

        for publication in publications:
            try:
                refresh_result = await self._refresh_publication(publication)
                results[publication.platform] = {
                    **results.get(publication.platform, {}),
                    **refresh_result,
                    "publication_id": publication.id,
                }
            except Exception as exc:
                results[publication.platform] = {
                    **results.get(publication.platform, {}),
                    "status": "failed",
                    "message": str(exc),
                    "publication_id": publication.id,
                    "retryable": True,
                    "next_action": "请稍后重试状态刷新，或检查平台账号授权。",
                }

        task.results = results
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get_task(self, task_id: str) -> PublishTaskRecord | None:
        return await self.session.get(PublishTaskRecord, task_id)

    async def get_publication(self, publication_id: str) -> PublicationRecord | None:
        return await self.session.get(PublicationRecord, publication_id)

    async def delete_publication(self, publication_id: str) -> PublicationDeleteResponse | None:
        publication = await self.get_publication(publication_id)
        if publication is None:
            return None

        if publication.platform != "bilibili":
            return PublicationDeleteResponse(
                publication_id=publication.id,
                platform=publication.platform,
                status=publication.status,
                message="当前平台不支持通过后端删除已提交发布内容。",
                details={},
            )

        if not publication.external_id:
            return PublicationDeleteResponse(
                publication_id=publication.id,
                platform=publication.platform,
                status=publication.status,
                message="发布记录没有平台外部 ID，无法删除。",
                details={},
            )

        credentials = await self._credentials_for_publication(publication)
        details = await BilibiliWebClient().delete_video(credentials, publication.external_id)
        publication.status = "deleted"
        publication.external_status = "deleted"
        publication.response_payload = {
            **(publication.response_payload or {}),
            "delete_response": details,
        }
        await self.session.commit()
        return PublicationDeleteResponse(
            publication_id=publication.id,
            platform=publication.platform,
            status=publication.status,
            message="Bilibili publication deleted.",
            details=details,
        )

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

    @staticmethod
    def publication_to_response(record: PublicationRecord) -> PublicationResponse:
        return PublicationResponse(
            publication_id=record.id,
            task_id=record.task_id,
            preview_id=record.preview_id,
            account_id=record.account_id,
            platform=record.platform,
            mode=record.mode,
            status=record.status,
            external_id=record.external_id,
            external_url=record.external_url,
            external_status=record.external_status,
            response_payload=record.response_payload,
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def _create_simulation_task(
        self,
        preview: PreviewRecord,
        request: PublishTaskCreateRequest,
        platforms: list[str],
    ) -> PublishTaskRecord:
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
            except Exception as exc:
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
            account_ids=dict(request.account_ids),
            asset_ids={platform: ids for platform, ids in request.asset_ids.items()},
            platform_options={platform: options for platform, options in request.platform_options.items()},
            results=results,
            error_message=error_message,
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    @staticmethod
    def _validate_real_publish_request(
        request: PublishTaskCreateRequest,
        platforms: list[str],
    ) -> None:
        unsupported = sorted(set(platforms) - REAL_PUBLISH_PLATFORMS)
        if unsupported:
            raise UnsupportedPublishModeError(
                "Real publish is only supported for wechat and bilibili in phase two. "
                f"Unsupported: {', '.join(unsupported)}."
            )
        for platform in platforms:
            if platform not in request.account_ids:
                raise UnsupportedPublishModeError(
                    f"account_ids.{platform} is required for real publish."
                )

    @staticmethod
    def _enqueue_real_publish(task_id: str) -> bool:
        try:
            from backend.app.tasks.publish import execute_publish_task
        except Exception:
            return False

        try:
            execute_publish_task.delay(task_id)
        except Exception:
            return False
        return True

    async def _build_account_context(
        self,
        task: PublishTaskRecord,
        platform: str,
    ) -> dict[str, Any]:
        account_id = task.account_ids.get(platform)
        if not account_id:
            raise PlatformClientError(
                f"Missing account_id for {platform}.",
                platform_code="ACCOUNT_REQUIRED",
            )

        account = await self.session.get(ConnectedAccountRecord, account_id)
        if account is None:
            raise PlatformClientError(
                f"Account {account_id} not found.",
                platform_code="ACCOUNT_NOT_FOUND",
                next_action="请重新连接账号并选择正确的 account_id。",
            )

        account_service = AccountService(self.session)
        credentials = await self._resolve_credentials(account, account_service)
        assets = await self._load_assets(task.asset_ids.get(platform, []))
        return {
            "account_id": account.id,
            "credentials": credentials,
            "assets": assets,
            "options": task.platform_options.get(platform, {}),
        }

    async def _load_assets(self, asset_ids: list[str]) -> list[LocalAsset]:
        if not asset_ids:
            return []
        result = await self.session.execute(
            select(ContentAssetRecord).where(ContentAssetRecord.id.in_(asset_ids))
        )
        records = result.scalars().all()
        return [
            LocalAsset(
                asset_id=record.id,
                asset_type=record.asset_type,
                purpose=record.purpose,
                original_filename=record.original_filename,
                content_type=record.content_type,
                file_path=record.file_path,
                file_size=record.file_size,
                sha256=record.sha256,
            )
            for record in records
        ]

    async def _list_publications_by_task(self, task_id: str) -> list[PublicationRecord]:
        result = await self.session.execute(
            select(PublicationRecord).where(PublicationRecord.task_id == task_id)
        )
        return list(result.scalars().all())

    async def _refresh_publication(self, publication: PublicationRecord) -> dict[str, Any]:
        credentials = await self._credentials_for_publication(publication)
        if publication.platform == "wechat":
            if publication.mode != PublishMode.PUBLISH or not publication.external_id:
                return {
                    "status": publication.status,
                    "external_status": publication.external_status,
                    "message": "WeChat draft status does not require refresh.",
                }
            token = await WechatOfficialAccountClient().get_access_token(
                credentials.get("app_id", ""),
                credentials.get("app_secret", ""),
            )
            details = await WechatOfficialAccountClient().get_publish_status(
                token["access_token"],
                publication.external_id,
            )
        elif publication.platform == "bilibili":
            if not publication.external_id:
                return {
                    "status": publication.status,
                    "external_status": publication.external_status,
                    "message": "Bilibili publication has no external_id yet.",
                }
            details = await BilibiliWebClient().get_video_status(credentials, publication.external_id)
        else:
            raise UnsupportedPublishModeError(f"{publication.platform} refresh is not supported.")

        data = details.get("data", details)
        publication.response_payload = {
            **(publication.response_payload or {}),
            "refresh_response": details,
        }
        publication.external_status = str(
            data.get("publish_status")
            or data.get("status")
            or data.get("state")
            or publication.external_status
        )
        publication.status = "succeeded"
        await self.session.commit()
        return {
            "platform": publication.platform,
            "status": publication.status,
            "external_status": publication.external_status,
            "message": "Publication status refreshed.",
            "raw_response": details,
        }

    async def _credentials_for_publication(self, publication: PublicationRecord) -> dict[str, Any]:
        if not publication.account_id:
            raise PlatformClientError(
                "Publication has no account_id.",
                platform_code="ACCOUNT_REQUIRED",
            )
        account = await self.session.get(ConnectedAccountRecord, publication.account_id)
        if account is None:
            raise PlatformClientError(
                "Connected account not found.",
                platform_code="ACCOUNT_NOT_FOUND",
            )
        account_service = AccountService(self.session)
        return await self._resolve_credentials(account, account_service)

    async def _resolve_credentials(
        self,
        account: ConnectedAccountRecord,
        account_service: AccountService,
    ) -> dict[str, Any]:
        credentials = account_service.decrypt_credentials(account)
        if account.platform != "bilibili":
            return credentials

        if not credentials.get("SESSDATA"):
            account.status = "expired"
            await self.session.commit()
            raise PlatformClientError(
                "B站登录凭据缺少 SESSDATA，无法执行真实发布。",
                platform_code="COOKIE_MISSING",
                next_action="请重新完成 B站登录。",
            )
        if not credentials.get("bili_jct"):
            account.status = "expired"
            await self.session.commit()
            raise PlatformClientError(
                "B站登录凭据缺少 bili_jct，无法执行需要 CSRF 的接口。",
                platform_code="CSRF_COOKIE_MISSING",
                next_action="请重新完成 B站登录。",
            )
        return credentials
