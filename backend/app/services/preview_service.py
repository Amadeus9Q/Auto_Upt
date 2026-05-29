from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.registry import select_adapters
from backend.app.models.content import PreviewRecord
from backend.app.schemas.content import (
    AdaptContentRequest,
    ContentInput,
    PreviewCreateRequest,
    PreviewResponse,
)


class PreviewService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    def normalize_content(self, request: ContentInput) -> dict[str, Any]:
        body = request.body.strip()
        title = self._normalize_title(request.title, body)
        tags = self._normalize_tags(request.tags)
        summary = self._summarize(body)

        return {
            "id": str(uuid4()),
            "title": title,
            "body": body,
            "summary": summary,
            "content_type": request.content_type,
            "tags": tags,
            "assets": [asset.model_dump() for asset in request.assets],
            "word_count": self._count_words(body),
            "created_at": datetime.now(UTC).isoformat(),
        }

    def adapt_content(
        self,
        request: AdaptContentRequest | PreviewCreateRequest,
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        content_ir = self.normalize_content(request)
        adapters = select_adapters(request.platforms)
        drafts: dict[str, dict[str, Any]] = {}
        validation_report: dict[str, list[dict[str, Any]]] = {}

        for platform, adapter in adapters.items():
            draft = adapter.render(content_ir)
            drafts[platform] = draft
            validation_report[platform] = adapter.validate(draft)

        return content_ir, drafts, validation_report

    async def create_preview(self, request: PreviewCreateRequest) -> PreviewRecord:
        if self.session is None:
            raise RuntimeError("PreviewService.create_preview requires a database session.")

        content_ir, drafts, validation_report = self.adapt_content(request)
        record = PreviewRecord(
            title=content_ir["title"],
            body=content_ir["body"],
            content_type=content_ir["content_type"],
            raw_input=request.model_dump(),
            content_ir=content_ir,
            drafts=drafts,
            validation_report=validation_report,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get_preview(self, preview_id: str) -> PreviewRecord | None:
        if self.session is None:
            raise RuntimeError("PreviewService.get_preview requires a database session.")
        return await self.session.get(PreviewRecord, preview_id)

    @staticmethod
    def to_response(record: PreviewRecord) -> PreviewResponse:
        return PreviewResponse(
            preview_id=record.id,
            content_ir=record.content_ir,
            drafts=record.drafts,
            validation_report=record.validation_report,
            created_at=record.created_at,
        )

    @staticmethod
    def _normalize_title(title: str | None, body: str) -> str:
        if title and title.strip():
            return title.strip()
        for line in body.splitlines():
            candidate = line.strip().lstrip("#").strip()
            if candidate:
                return candidate[:80]
        return "Untitled Content"

    @staticmethod
    def _normalize_tags(tags: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for tag in tags:
            value = tag.strip().lstrip("#")
            key = value.casefold()
            if value and key not in seen:
                normalized.append(value)
                seen.add(key)
        return normalized

    @staticmethod
    def _summarize(body: str) -> str:
        for paragraph in body.splitlines():
            candidate = paragraph.strip().lstrip("#").strip()
            if candidate:
                return candidate[:160]
        return body[:160]

    @staticmethod
    def _count_words(body: str) -> int:
        if any(char.isspace() for char in body):
            return len([part for part in body.split() if part.strip()])
        return len(body)
