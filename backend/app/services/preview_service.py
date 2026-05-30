from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.registry import select_adapters
from backend.app.agents.content_analyst import ContentAnalystAgent
from backend.app.agents.platform_stylist import PlatformStylistAgent
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
        self.content_analyst = ContentAnalystAgent()
        self.platform_stylist = PlatformStylistAgent()

    def normalize_content(self, request: ContentInput) -> dict[str, Any]:
        body = request.body.strip()
        title = self._normalize_title(request.title, body)
        tags = self._normalize_tags(request.tags)
        summary = self._summarize(body)
        assets = [asset.model_dump() for asset in request.assets]
        body_blocks = self._normalize_blocks(body, assets, [block.model_dump() for block in request.content_blocks])

        # ---- 深度内容分析：章节划分 + 媒体识别 ----
        analysis = self.content_analyst.analyze(
            body=body,
            title=title,
            tags=tags,
            content_blocks=body_blocks,
            assets=assets,
            content_type=request.content_type,
        )

        return {
            "id": str(uuid4()),
            "title": title,
            "body": body,
            "summary": summary,
            "subtitle": analysis.subtitle,
            "content_type": request.content_type,
            "tags": tags,
            "assets": assets,
            "body_blocks": body_blocks,
            "media_slots": self._build_media_slots(assets, body_blocks, request.cover_asset_id),
            "cover_asset_id": request.cover_asset_id,
            "word_count": self._count_words(body),
            # 新增：章节和媒体分析结果
            "chapters": [ch.model_dump() for ch in analysis.chapters],
            "flat_chapters": [ch.model_dump() for ch in analysis.flat_chapters],
            "all_media": [m.model_dump() for m in analysis.all_media],
            "media_by_kind": {
                k: [m.model_dump() for m in v]
                for k, v in analysis.media_by_kind.items()
            },
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
            validation_report[platform] = adapter.validate(draft) + self._validate_media_for_platform(platform, draft)

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

    @staticmethod
    def _normalize_blocks(body: str, assets: list[dict[str, Any]], blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        asset_map = {asset.get("id"): asset for asset in assets if asset.get("id")}
        normalized: list[dict[str, Any]] = []

        source_blocks = blocks or PreviewService._parse_asset_markers(body)
        for block in source_blocks:
            if block.get("type") == "text":
                text = (block.get("text") or "").strip()
                if text:
                    normalized.append({"type": "text", "text": text})
                continue

            asset_id = block.get("asset_id")
            asset = asset_map.get(asset_id)
            if not asset:
                continue
            kind = block.get("asset_kind") or asset.get("type")
            normalized.append(
                {
                    "type": "asset",
                    "asset_id": asset_id,
                    "asset_kind": kind,
                    "role": block.get("role") or "inline",
                    "asset": asset,
                }
            )

        if not normalized and body:
            normalized.append({"type": "text", "text": body})
        return normalized

    @staticmethod
    def _parse_asset_markers(body: str) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        pattern = re.compile(r"\{\{asset:(image|video|audio):([^}]+)\}\}")
        cursor = 0

        for match in pattern.finditer(body):
            text = body[cursor : match.start()].strip()
            if text:
                blocks.append({"type": "text", "text": text})
            blocks.append({"type": "asset", "asset_kind": match.group(1), "asset_id": match.group(2), "role": "inline"})
            cursor = match.end()

        trailing_text = body[cursor:].strip()
        if trailing_text:
            blocks.append({"type": "text", "text": trailing_text})
        return blocks

    @staticmethod
    def _build_media_slots(
        assets: list[dict[str, Any]],
        body_blocks: list[dict[str, Any]],
        cover_asset_id: str | None,
    ) -> dict[str, Any]:
        asset_map = {asset.get("id"): asset for asset in assets if asset.get("id")}
        cover = asset_map.get(cover_asset_id) if cover_asset_id else None
        if cover is None:
            cover = next((asset for asset in assets if asset.get("usage") == "default_cover"), None)
        if cover is None:
            cover = next((asset for asset in assets if asset.get("type") in ("cover", "image")), None)

        body_assets = [block["asset"] for block in body_blocks if block.get("type") == "asset" and block.get("asset")]
        return {
            "cover": cover,
            "main_video": next((asset for asset in assets if asset.get("usage") == "bilibili_video"), None),
            "body_images": [asset for asset in body_assets if asset.get("type") in ("image", "body_image")],
            "body_videos": [asset for asset in body_assets if asset.get("type") == "video"],
            "body_audios": [asset for asset in body_assets if asset.get("type") == "audio"],
            "unsupported": [],
        }

    @staticmethod
    def _validate_media_for_platform(platform: str, draft: dict[str, Any]) -> list[dict[str, Any]]:
        slots = draft.get("media_slots") or {}
        issues: list[dict[str, Any]] = []

        if platform == "bilibili":
            if not slots.get("main_video"):
                issues.append(
                    {
                        "level": "error",
                        "code": "BILIBILI_VIDEO_REQUIRED",
                        "field": "media_slots.main_video",
                        "message": "B站真实发布需要选择一个视频文件。",
                    }
                )
            if not slots.get("cover"):
                issues.append(
                    {
                        "level": "warning",
                        "code": "BILIBILI_COVER_RECOMMENDED",
                        "field": "media_slots.cover",
                        "message": "建议为 B站稿件选择封面图。",
                    }
                )

        if platform == "wechat":
            if slots.get("body_videos") or slots.get("body_audios"):
                issues.append(
                    {
                        "level": "warning",
                        "code": "WECHAT_INLINE_MEDIA_PLACEHOLDER",
                        "field": "body_blocks",
                        "message": "公众号正文中的视频和音频当前仅作为预览占位，真实上传规则需在后续联调中确认。",
                    }
                )

        if platform in {"zhihu", "xiaohongshu"} and (slots.get("body_videos") or slots.get("body_audios")):
            issues.append(
                {
                    "level": "info",
                    "code": "BROWSER_ASSISTED_MEDIA_PENDING",
                    "field": "body_blocks",
                    "message": "该平台的多媒体真实发布将在第三阶段浏览器辅助发布中接入。",
                }
            )

        return issues
