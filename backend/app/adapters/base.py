from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml


class UnsupportedPublishModeError(ValueError):
    pass


def load_profile(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as profile_file:
        profile = yaml.safe_load(profile_file) or {}
    return profile


def split_paragraphs(body: str) -> list[str]:
    return [line.strip() for line in body.splitlines() if line.strip()]


def clip_text(text: str, max_length: int, suffix: str = "...") -> str:
    if len(text) <= max_length:
        return text
    if max_length <= len(suffix):
        return text[:max_length]
    return text[: max_length - len(suffix)].rstrip() + suffix


def clip_tag(tag: str, max_length: int = 8) -> str:
    """截断单个标签，保留最多 max_length 个字符（约 1-3 个中文词）。"""
    tag = tag.strip()
    if len(tag) <= max_length:
        return tag
    return tag[:max_length]


def clip_tags(tags: list[str], *, max_length: int = 8, max_count: int | None = None) -> list[str]:
    """截断标签列表：每个标签不超过 max_length 字符，可选限制总数。"""
    result = [clip_tag(t, max_length) for t in tags if t.strip()]
    if max_count is not None:
        result = result[:max_count]
    return result


def first_non_empty(*values: str | None, fallback: str = "Untitled Content") -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return fallback


class PlatformAdapter(ABC):
    def __init__(self, profile: dict[str, Any]) -> None:
        self.profile = profile
        self.platform = profile["platform"]
        self.display_name = profile.get("display_name", self.platform)

    def capabilities(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "display_name": self.display_name,
            "content_types": self.profile.get("content_types", []),
            "publish_modes": self.profile.get("publish_modes", ["simulate"]),
            "auth": self.profile.get("auth", {}),
            "limits": self.profile.get("limits", {}),
        }

    @abstractmethod
    def render(self, content_ir: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def validate(self, draft: dict[str, Any]) -> list[dict[str, Any]]:
        limits = self.profile.get("limits", {})
        issues: list[dict[str, Any]] = []

        tags = draft.get("tags", [])
        assets = draft.get("assets", [])

        tags_max = limits.get("tags_max_count")
        if tags_max and len(tags) > tags_max:
            issues.append(
                {
                    "level": "warning",
                    "code": "TOO_MANY_TAGS",
                    "field": "tags",
                    "message": f"Tag count exceeds {tags_max}.",
                }
            )

        min_assets = limits.get("assets_min_count", 0)
        if len(assets) < min_assets:
            issues.append(
                {
                    "level": "info",
                    "code": "ASSET_SUGGESTED",
                    "field": "assets",
                    "message": f"At least {min_assets} asset(s) are recommended.",
                }
            )

        return issues

    def simulate(self, draft: dict[str, Any]) -> dict[str, Any]:
        screenshot_id = uuid4().hex
        return {
            "platform": self.platform,
            "display_name": self.display_name,
            "mode": "simulate",
            "status": "succeeded",
            "preview": draft,
            "preview_url": f"mock://{self.platform}/previews/{screenshot_id}",
            "screenshot_path": f"storage/screenshots/{self.platform}-{screenshot_id}.png",
            "message": "Simulated publish completed. No external platform was called.",
        }

    async def publish(
        self,
        draft: dict[str, Any],
        account: dict[str, Any] | None = None,
        mode: str = "simulate",
    ) -> dict[str, Any]:
        if mode != "simulate":
            raise UnsupportedPublishModeError(
                f"{self.display_name} real publish is not supported in the MVP."
            )
        return self.simulate(draft)
