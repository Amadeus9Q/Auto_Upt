from pathlib import Path
from typing import Any

from backend.app.adapters.base import PlatformAdapter, load_profile
from backend.app.adapters.wechat.renderer import render_draft


class WechatAdapter(PlatformAdapter):
    def __init__(self) -> None:
        profile_path = Path(__file__).with_name("profile.yaml")
        super().__init__(load_profile(profile_path))

    def render(self, content_ir: dict[str, Any]) -> dict[str, Any]:
        return render_draft(content_ir, self.profile)
