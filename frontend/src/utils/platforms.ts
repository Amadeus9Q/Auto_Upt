import type { PlatformKey, AgentStyleGoal } from "@/api/client";

export const PLATFORM_LABELS: Record<PlatformKey, string> = {
  wechat: "公众号",
  bilibili: "B站",
  zhihu: "知乎",
  xiaohongshu: "小红书",
};

export const PLATFORM_AGENT_STYLE_GOALS: Record<PlatformKey, AgentStyleGoal> = {
  wechat: "professional",
  bilibili: "video",
  zhihu: "knowledge",
  xiaohongshu: "social",
};

export const REAL_PUBLISH_PLATFORMS: PlatformKey[] = ["wechat", "bilibili", "xiaohongshu"];

export const PUBLISHABLE_PLATFORMS: PlatformKey[] = ["wechat", "bilibili", "xiaohongshu"];
