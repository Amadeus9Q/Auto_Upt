from backend.app.adapters.base import PlatformAdapter
from backend.app.adapters.bilibili.adapter import BilibiliAdapter
from backend.app.adapters.wechat.adapter import WechatAdapter
from backend.app.adapters.xiaohongshu.adapter import XiaohongshuAdapter
from backend.app.adapters.zhihu.adapter import ZhihuAdapter


_ADAPTERS: dict[str, PlatformAdapter] = {
    adapter.platform: adapter
    for adapter in (
        WechatAdapter(),
        ZhihuAdapter(),
        XiaohongshuAdapter(),
        BilibiliAdapter(),
    )
}


def list_adapters() -> dict[str, PlatformAdapter]:
    return dict(_ADAPTERS)


def default_platforms() -> list[str]:
    return list(_ADAPTERS.keys())


def get_adapter(platform: str) -> PlatformAdapter:
    try:
        return _ADAPTERS[platform]
    except KeyError as exc:
        supported = ", ".join(sorted(_ADAPTERS))
        raise KeyError(f"Unsupported platform '{platform}'. Supported: {supported}.") from exc


def select_adapters(platforms: list[str] | None = None) -> dict[str, PlatformAdapter]:
    if not platforms:
        return list_adapters()
    return {platform: get_adapter(platform) for platform in platforms}
