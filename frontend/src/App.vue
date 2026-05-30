<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowDown, ArrowRight, Check, Monitor, Operation, Right, User, VideoPlay, WarningFilled } from "@element-plus/icons-vue";

import {
  createPreview,
  createPublishTask,
  getAccounts,
  listPublishTasks,
  publishDraftPublication,
  refreshPublishTask,
  runAgentAdaptPreview,
  updatePreviewDraft,
  uploadAsset,
  type AgentStyleGoal,
  type AssetPayload,
  type ContentPayload,
  type ContentBlockPayload,
  type PlatformKey,
  type PreviewDraftUpdatePayload,
  type PreviewResponse,
  type PublishMode,
  type PublishTaskCreatePayload,
  type PublishTaskResponse
} from "@/api/client";
import AccountView from "@/views/AccountView.vue";
import EditorView, { type EditorAssets, type LocalAsset } from "@/views/EditorView.vue";
import PreviewView, { type PlatformDraft } from "@/views/PreviewView.vue";
import PublishConfirmView from "@/views/PublishConfirmView.vue";
import PublishFormView, { type PublishForms } from "@/views/PublishFormView.vue";
import TaskView from "@/views/TaskView.vue";

type WorkspaceTab = "preview" | "confirm" | "task" | "account";
type TaskStep = {
  name: string;
  state: "wait" | "process" | "finish" | "error" | "success";
};

const platformLabels: Record<PlatformKey, string> = {
  wechat: "公众号",
  bilibili: "B站",
  zhihu: "知乎",
  xiaohongshu: "小红书"
};

const realPublishPlatforms: PlatformKey[] = ["wechat", "bilibili"];
const bilibiliTidByCategory: Record<string, number> = {
  tech: 201,
  knowledge: 124,
  life: 21
};
const platformAgentStyleGoal: Record<PlatformKey, AgentStyleGoal> = {
  wechat: "professional",
  bilibili: "video",
  zhihu: "knowledge",
  xiaohongshu: "social"
};
const allPlatforms: PlatformKey[] = ["wechat", "bilibili", "zhihu", "xiaohongshu"];

const activeTab = ref<WorkspaceTab>("preview");
const title = ref("");
const content = ref("");
const tags = ref("");
const selectedPlatforms = ref<PlatformKey[]>(["wechat", "bilibili", "zhihu", "xiaohongshu"]);
const editorAssets = ref<EditorAssets>({
  images: [],
  videos: [],
  audios: [],
  coverImage: null,
  coverImageId: null
});
const publishForms = ref<PublishForms>({
  bilibili: {
    title: title.value,
    description: content.value,
    tags: tags.value,
    category: ""
  },
  wechat: {
    title: title.value,
    summary: content.value.slice(0, 80),
    author: "Auto_Upt",
    directPublish: false
  }
});
const preview = ref<PreviewResponse | null>(null);
const task = ref<PublishTaskResponse | null>(null);
const tasks = ref<PublishTaskResponse[]>([]);
const previewLoading = ref(false);
const agentLoading = ref(false);
const taskLoading = ref(false);
const taskHistoryLoading = ref(false);
const taskActionLoading = ref<string | null>(null);
const errorMessage = ref("");
const previewDialogVisible = ref(false);
const previewDialogPlatform = ref<PlatformKey>("wechat");
const publishFormExpanded = ref<string[]>([]);
const draftSyncTimers = new Map<PlatformKey, number>();

const wordCount = computed(() => content.value.replace(/\s/g, "").length);

const tagList = computed(() =>
  tags.value
    .split(/[,，\s]+/)
    .map((tag) => tag.trim())
    .filter(Boolean)
);

const tabSubtitle = computed(() => {
  const subtitles: Record<WorkspaceTab, string> = {
    preview: "内容预览",
    confirm: "发布确认",
    task: "任务看板",
    account: "账号管理"
  };
  return subtitles[activeTab.value] ?? "内容预览";
});

const validationReport = computed(() => preview.value?.validation_report ?? {});

const drafts = computed<PlatformDraft[]>(() => {
  if (!preview.value) {
    return [];
  }

  return Object.entries(preview.value.drafts).map(([key, draft]) => {
    const platform = key as PlatformKey;
    const issues = preview.value?.validation_report[platform] ?? [];
    const warnings = issues.filter((issue) => issue.level === "warning" || issue.level === "error").length;

    return {
      key: platform,
      label: platformLabels[platform],
      title: draft?.title ?? platformLabels[platform],
      summary: draft?.summary || draft?.body || "暂无摘要。",
      body: draft?.body ?? "",
      tags: draft?.tags ?? [],
      status: warnings > 0 ? "warning" : "ready",
      issues,
      rich_body: draft?.rich_body ?? [],
      cover_image: draft?.cover_image ?? null,
      body_blocks: draft?.body_blocks ?? [],
      media_slots: draft?.media_slots ?? {},
      author: draft?.author || "Auto_Upt",
      metadata: draft?.metadata,
      metrics: [
        { label: "标题", value: `${draft?.title?.length ?? 0} 字` },
        { label: "正文", value: `${draft?.body?.length ?? 0} 字` },
        { label: "校验", value: `${issues.length} 项` }
      ]
    };
  });
});

const taskSteps = computed<TaskStep[]>(() => {
  const middleStep = task.value?.mode === "draft" ? "创建草稿" : task.value?.mode === "simulate" ? "模拟校验" : "平台处理";
  const finalStep = task.value?.mode === "draft" ? "草稿已创建" : task.value?.mode === "simulate" ? "模拟完成" : "已发布";

  if (!task.value && taskLoading.value) {
    return [
      { name: "提交中", state: "process" },
      { name: middleStep, state: "wait" },
      { name: finalStep, state: "wait" }
    ];
  }

  if (!task.value) {
    return [
      { name: "提交中", state: "wait" },
      { name: middleStep, state: "wait" },
      { name: finalStep, state: "wait" }
    ];
  }

  if (task.value.status === "failed") {
    return [
      { name: "提交中", state: "finish" },
      { name: middleStep, state: "error" },
      { name: "失败", state: "error" }
    ];
  }

  return [
    { name: "提交中", state: "finish" },
    { name: middleStep, state: "finish" },
    { name: finalStep, state: "finish" }
  ];
});

watch(title, (nextTitle) => {
  publishForms.value.bilibili.title = nextTitle;
  publishForms.value.wechat.title = nextTitle;
});

watch(tags, (nextTags) => {
  publishForms.value.bilibili.tags = nextTags;
});

function assetToPayload(asset: LocalAsset, type: AssetPayload["type"], usage: string): AssetPayload {
  return {
    id: asset.id,
    name: asset.name,
    type,
    size: asset.size,
    mime_type: asset.mimeType,
    usage,
    preview_url: asset.previewUrl
  };
}

function collectAssetPayloads(): AssetPayload[] {
  const coverImageId = editorAssets.value.coverImageId ?? editorAssets.value.images[0]?.id;

  return [
    ...(editorAssets.value.coverImage ? [assetToPayload(editorAssets.value.coverImage, "cover", "default_cover")] : []),
    ...editorAssets.value.images.map((asset) => assetToPayload(asset, "image", asset.id === coverImageId ? "default_cover" : "body_image")),
    ...editorAssets.value.videos.map((asset, index) => assetToPayload(asset, "video", index === 0 ? "bilibili_video" : "reference_video")),
    ...editorAssets.value.audios.map((asset) => assetToPayload(asset, "audio", "reference_audio"))
  ];
}

function collectContentBlocks(): ContentBlockPayload[] {
  const assetMap = new Map<string, LocalAsset>();
  const assetByDisplayToken = new Map<string, LocalAsset>();
  for (const asset of [...editorAssets.value.images, ...editorAssets.value.videos, ...editorAssets.value.audios]) {
    assetMap.set(asset.id, asset);
    const kindLabel = asset.kind === "image" ? "图片" : asset.kind === "video" ? "视频" : "音频";
    assetByDisplayToken.set(`${kindLabel}:${asset.name}`, asset);
  }

  const blocks: ContentBlockPayload[] = [];
  const markerPattern = /\{\{asset:(image|video|audio):([^}]+)\}\}|【(图片|视频|音频)：([^】]+)】/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = markerPattern.exec(content.value)) !== null) {
    const text = content.value.slice(cursor, match.index).trim();
    if (text) {
      blocks.push({ type: "text", text });
    }

    const asset = match[1]
      ? assetMap.get(match[2])
      : assetByDisplayToken.get(`${match[3]}:${match[4]}`);
    if (asset) {
      blocks.push({ type: "asset", asset_id: asset.id, asset_kind: asset.kind, role: "inline" });
    }
    cursor = match.index + match[0].length;
  }

  const trailingText = content.value.slice(cursor).trim();
  if (trailingText) {
    blocks.push({ type: "text", text: trailingText });
  }

  if (!blocks.length && content.value.trim()) {
    blocks.push({ type: "text", text: content.value.trim() });
  }

  return blocks;
}

function buildContentPayload(): ContentPayload {
  return {
    title: title.value.trim() || undefined,
    body: content.value,
    content_type: editorAssets.value.videos.length ? "video" : collectAssetPayloads().length ? "mixed" : "article",
    tags: tagList.value,
    assets: collectAssetPayloads(),
    content_blocks: collectContentBlocks(),
    cover_asset_id: editorAssets.value.coverImage?.id ?? editorAssets.value.coverImageId ?? null,
    platforms: selectedPlatforms.value
  };
}

function previewFromAgentRun(run: Awaited<ReturnType<typeof runAgentAdaptPreview>>): PreviewResponse {
  return {
    preview_id: run.preview_id ?? "",
    content_ir: run.content_ir,
    drafts: run.drafts,
    validation_report: run.validation_report,
    created_at: run.created_at
  };
}

function scheduleDraftSync(platform: PlatformKey) {
  if (!preview.value?.preview_id) {
    return;
  }
  const draft = preview.value.drafts[platform];
  if (!draft) {
    return;
  }

  const existingTimer = draftSyncTimers.get(platform);
  if (existingTimer) {
    window.clearTimeout(existingTimer);
  }

  const previewId = preview.value.preview_id;
  const payload: PreviewDraftUpdatePayload = {
    title: draft.title,
    body: draft.body,
    summary: draft.summary,
    tags: draft.tags
  };
  const timer = window.setTimeout(async () => {
    try {
      const updated = await updatePreviewDraft(previewId, platform, payload);
      // 只更新 validation_report，不覆盖用户正在编辑的草稿内容
      if (preview.value) {
        preview.value = {
          ...preview.value,
          validation_report: {
            ...preview.value.validation_report,
            ...updated.validation_report
          }
        };
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "同步草稿失败，请检查网络连接。";
      errorMessage.value = message;
      ElMessage.error(message);
    } finally {
      draftSyncTimers.delete(platform);
    }
  }, 600);
  draftSyncTimers.set(platform, timer);
}

function updatePlatformDraft(platform: PlatformKey, patch: PreviewDraftUpdatePayload) {
  if (!preview.value) {
    return;
  }
  const currentDraft = preview.value.drafts[platform];
  if (!currentDraft) {
    return;
  }
  preview.value = {
    ...preview.value,
    drafts: {
      ...preview.value.drafts,
      [platform]: {
        ...currentDraft,
        ...patch
      }
    }
  };
  scheduleDraftSync(platform);
}

function createFailedLocalTask(previewId: string, platforms: PlatformKey[], mode: PublishMode, message: string): PublishTaskResponse {
  return {
    task_id: `local-failed-${Date.now()}`,
    preview_id: previewId,
    mode,
    status: "failed",
    platforms,
    results: Object.fromEntries(
      platforms.map((platform) => [
        platform,
        {
          platform,
          display_name: platformLabels[platform],
          mode,
          status: "failed",
          message
        }
      ])
    ),
    error_message: message,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  };
}

function getCoverImage(): LocalAsset | null {
  return editorAssets.value.coverImage ?? editorAssets.value.images.find((image) => image.id === editorAssets.value.coverImageId) ?? editorAssets.value.images[0] ?? null;
}

function getUploadAssetType(asset: LocalAsset): "image" | "video" | "file" {
  if (asset.kind === "image" || asset.kind === "video") {
    return asset.kind;
  }
  return "file";
}

async function ensureBackendAsset(asset: LocalAsset, purpose: string): Promise<string> {
  if (asset.backendAssetId) {
    return asset.backendAssetId;
  }

  const uploaded = await uploadAsset(asset.file, getUploadAssetType(asset), purpose);
  asset.backendAssetId = uploaded.asset_id;
  asset.backendUrl = uploaded.url;
  asset.uploadPurpose = purpose;
  return uploaded.asset_id;
}

function parseTagText(value: string): string[] {
  return value
    .split(/[,，\s]+/)
    .map((tag) => tag.trim())
    .filter(Boolean);
}

async function resolveConnectedAccountIds(platforms: PlatformKey[]): Promise<Partial<Record<PlatformKey, string>>> {
  const accounts = await getAccounts();
  const accountIds: Partial<Record<PlatformKey, string>> = {};

  for (const platform of platforms) {
    const account = accounts.find((item) => item.platform === platform && item.status === "connected" && item.account_id);
    if (!account?.account_id) {
      throw new Error(`请先在「账号管理」中连接${platformLabels[platform]}账号，再执行发布操作。`);
    }
    accountIds[platform] = account.account_id;
  }

  return accountIds;
}

async function buildPublishTaskPayload(payload: { platforms: PlatformKey[]; mode: PublishMode }): Promise<PublishTaskCreatePayload> {
  if (!preview.value) {
    throw new Error("请先生成内容预览。");
  }

  if (payload.mode === "simulate") {
    return {
      preview_id: preview.value.preview_id,
      mode: payload.mode,
      platforms: payload.platforms,
      inline_drafts: preview.value.drafts,
      inline_content_ir: preview.value.content_ir
    };
  }

  const platforms = payload.platforms.filter((platform) => realPublishPlatforms.includes(platform));
  if (!platforms.length) {
    throw new Error("当前版本草稿及真实发布仅支持公众号与 B 站。");
  }
  if (platforms.length !== payload.platforms.length) {
    throw new Error("知乎和小红书当前版本不支持草稿及真实发布，请使用模拟发布。");
  }

  const accountIds = await resolveConnectedAccountIds(platforms);
  const assetIds: NonNullable<PublishTaskCreatePayload["asset_ids"]> = {};
  const platformOptions: NonNullable<PublishTaskCreatePayload["platform_options"]> = {};

  if (platforms.includes("wechat")) {
    const cover = getCoverImage();
    if (!cover) {
      throw new Error("公众号发布需要先上传封面图。");
    }

    const coverAssetId = await ensureBackendAsset(cover, "wechat_cover");
    const wechatAssetIds = new Set<string>([coverAssetId]);
    for (const image of editorAssets.value.images) {
      wechatAssetIds.add(await ensureBackendAsset(image, image.id === cover.id ? "wechat_cover" : "wechat_body_image"));
    }

    assetIds.wechat = [...wechatAssetIds];
    const wechatDraft = preview.value.drafts.wechat;
    platformOptions.wechat = {
      title: publishForms.value.wechat.title.trim() || wechatDraft?.title || title.value.trim(),
      author: publishForms.value.wechat.author.trim() || "匿名",
      digest: publishForms.value.wechat.summary.trim() || wechatDraft?.summary || "",
      cover_asset_id: coverAssetId,
      need_open_comment: false,
      only_fans_can_comment: false,
      direct_publish: publishForms.value.wechat.directPublish
    };
  }

  if (platforms.includes("bilibili")) {
    const video = editorAssets.value.videos[0] ?? null;
    if (!video) {
      throw new Error("B 站发布需要先上传视频文件。");
    }

    const cover = getCoverImage();
    const videoAssetId = await ensureBackendAsset(video, "bilibili_video");
    const coverAssetId = cover ? await ensureBackendAsset(cover, "bilibili_cover") : undefined;
    assetIds.bilibili = coverAssetId ? [videoAssetId, coverAssetId] : [videoAssetId];

    const category = publishForms.value.bilibili.category;
    const bilibiliDraft = preview.value.drafts.bilibili;
    platformOptions.bilibili = {
      title: publishForms.value.bilibili.title.trim() || bilibiliDraft?.title || title.value.trim(),
      description: publishForms.value.bilibili.description.trim() || bilibiliDraft?.body || content.value,
      tags: parseTagText(publishForms.value.bilibili.tags).length
        ? parseTagText(publishForms.value.bilibili.tags)
        : bilibiliDraft?.tags ?? [],
      video_asset_id: videoAssetId,
      cover_asset_id: coverAssetId,
      tid: bilibiliTidByCategory[category] ?? 201,
      copyright: 1,
      source: "",
      no_reprint: true,
      dynamic: ""
    };
  }

  return {
    preview_id: preview.value.preview_id,
    mode: payload.mode,
    platforms,
    account_ids: accountIds,
    asset_ids: assetIds,
    platform_options: platformOptions,
    inline_drafts: preview.value.drafts,
    inline_content_ir: preview.value.content_ir
  };
}

function upsertTask(nextTask: PublishTaskResponse) {
  task.value = nextTask;
  tasks.value = [nextTask, ...tasks.value.filter((item) => item.task_id !== nextTask.task_id)];
}

async function loadPublishTasks(showToast = false) {
  taskHistoryLoading.value = true;
  try {
    tasks.value = await listPublishTasks({ limit: 20 });
    task.value = tasks.value[0] ?? null;
    if (showToast) {
      ElMessage.success("任务列表已刷新。");
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "加载任务列表失败。";
    errorMessage.value = message;
    if (showToast) {
      ElMessage.error(message);
    }
  } finally {
    taskHistoryLoading.value = false;
  }
}

async function refreshTaskStatus(taskId: string) {
  taskActionLoading.value = `refresh:${taskId}`;
  try {
    const nextTask = await refreshPublishTask(taskId);
    upsertTask(nextTask);
    ElMessage.success("任务状态已更新。");
  } catch (error) {
    const message = error instanceof Error ? error.message : "更新任务状态失败。";
    errorMessage.value = message;
    ElMessage.error(message);
  } finally {
    taskActionLoading.value = null;
  }
}

async function publishDraftFromTask(publicationId: string) {
  try {
    await ElMessageBox.confirm("确认提交该草稿至平台发布？提交后将调用平台官方接口进行发布。", "确认发布草稿", {
      confirmButtonText: "确认",
      cancelButtonText: "取消",
      type: "warning"
    });
  } catch {
    return;
  }

  taskActionLoading.value = `publish:${publicationId}`;
  try {
    await publishDraftPublication(publicationId);
    await loadPublishTasks(false);
    ElMessage.success("草稿已提交至发布队列。");
  } catch (error) {
    const message = error instanceof Error ? error.message : "提交发布请求失败。";
    errorMessage.value = message;
    ElMessage.error(message);
  } finally {
    taskActionLoading.value = null;
  }
}

async function generatePreview() {
  // 输入文本框为空，不做处理
  if (!content.value.trim()) {
    return;
  }

  // 调用后端生成预览，填充平台预览文本框
  previewLoading.value = true;
  errorMessage.value = "";
  task.value = null;

  try {
    preview.value = await createPreview(buildContentPayload());
    ElMessage.success("预览已生成。");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "预览生成失败，请稍后重试。";
    ElMessage.error("预览生成失败，请稍后重试。");
  } finally {
    previewLoading.value = false;
  }
}

async function optimizeAllWithAgent() {
  if (!content.value.trim()) {
    ElMessage.warning("请先输入正文内容。");
    return;
  }

  agentLoading.value = true;
  errorMessage.value = "";

  try {
    const basePayload = buildContentPayload();
    const run = await runAgentAdaptPreview({
      ...basePayload,
      preview_id: preview.value?.preview_id ?? null,
      platforms: allPlatforms,
      style_goal: editorAssets.value.videos.length ? "video" : "professional",
      rewrite_strength: "medium",
      overwrite_existing_metadata: false,
      use_llm: "auto",
      persist_preview: !preview.value
    });

    if (!preview.value) {
      preview.value = previewFromAgentRun(run);
    } else {
      preview.value = {
        ...preview.value,
        drafts: {
          ...preview.value.drafts,
          ...run.drafts
        },
        validation_report: {
          ...preview.value.validation_report,
          ...run.validation_report
        }
      };
    }
    ElMessage.success("四个平台 Agent 优化结果已生成。");
  } catch (error) {
    const message = error instanceof Error ? error.message : "Agent 优化失败。";
    errorMessage.value = message;
    ElMessage.error(message);
  } finally {
    agentLoading.value = false;
  }
}

async function optimizeWithAgent(platform: PlatformKey) {
  if (!content.value.trim()) {
    ElMessage.warning("请先输入正文内容。");
    return;
  }
  if (!preview.value) {
    ElMessage.warning("请先生成预览，再优化当前平台内容。");
    return;
  }

  agentLoading.value = true;
  errorMessage.value = "";

  try {
    const basePayload = buildContentPayload();
    const run = await runAgentAdaptPreview({
      ...basePayload,
      preview_id: preview.value.preview_id,
      title: basePayload.title,
      body: basePayload.body,
      tags: basePayload.tags,
      platforms: [platform],
      style_goal: platformAgentStyleGoal[platform],
      rewrite_strength: "medium",
      overwrite_existing_metadata: false,
      use_llm: "auto",
      persist_preview: false
    });
    const optimizedDraft = run.drafts[platform];
    if (!optimizedDraft) {
      throw new Error(`${platformLabels[platform]}没有返回可用的优化草稿。`);
    }
    preview.value = {
      ...preview.value,
      drafts: {
        ...preview.value.drafts,
        [platform]: optimizedDraft
      },
      validation_report: {
        ...preview.value.validation_report,
        [platform]: run.validation_report[platform] ?? []
      }
    };
    ElMessage.success(`${platformLabels[platform]}内容已优化。`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Agent 优化失败。";
    errorMessage.value = message;
    ElMessage.error(message);
  } finally {
    agentLoading.value = false;
  }
}

function enterPublishConfirm() {
  if (!preview.value) {
    ElMessage.warning("请先生成预览。");
    return;
  }
  previewDialogVisible.value = false;
  activeTab.value = "confirm";
}

async function submitPublish(payload: { platforms: PlatformKey[]; mode: PublishMode }) {
  if (!preview.value) {
    ElMessage.warning("请先生成预览。");
    return;
  }

  if (payload.mode === "draft" || payload.mode === "publish") {
    try {
      await ElMessageBox.confirm(
        payload.mode === "publish"
          ? "确认后会调用真实平台接口提交发布。请确认账号、素材和平台规则已经检查无误。"
          : "确认后会调用真实平台接口创建草稿。请确认账号和素材已经检查无误。",
        "真实平台操作确认",
        {
          confirmButtonText: "确认调用",
          cancelButtonText: "取消",
          type: "warning"
        }
      );
    } catch {
      return;
    }
  }

  taskLoading.value = true;
  errorMessage.value = "";
  activeTab.value = "task";

  try {
    upsertTask(await createPublishTask(await buildPublishTaskPayload(payload)));
    ElMessage.success(payload.mode === "simulate" ? "模拟发布任务已创建。" : "发布任务已提交。");
  } catch (error) {
    const message = error instanceof Error ? error.message : "创建发布任务失败。";
    const failedTask = createFailedLocalTask(preview.value.preview_id, payload.platforms, payload.mode, message);
    task.value = failedTask;
    tasks.value = [failedTask, ...tasks.value];
    errorMessage.value = message;
    ElMessage.error("发布任务提交失败，已在任务看板展示原因。");
  } finally {
    taskLoading.value = false;
  }
}

function selectTab(key: string) {
  activeTab.value = key as WorkspaceTab;
}

function openPreviewDialog(platform?: PlatformKey) {
  previewDialogPlatform.value = platform ?? "wechat";
  previewDialogVisible.value = true;
}

onMounted(() => {
  void loadPublishTasks(false);
});
</script>

<template>
  <el-container class="app-shell">
    <el-aside class="sidebar" width="236px">
      <div class="brand">
        <el-icon :size="28"><VideoPlay /></el-icon>
        <div>
          <strong>Auto_Upt</strong>
          <span>内容发布助手</span>
        </div>
      </div>

      <el-menu :default-active="activeTab" class="nav-menu" @select="selectTab">
        <el-menu-item index="preview">
          <el-icon><Monitor /></el-icon>
          <span>内容预览</span>
        </el-menu-item>
        <el-menu-item index="confirm" :disabled="!preview">
          <el-icon><Check /></el-icon>
          <span>发布确认</span>
        </el-menu-item>
        <el-menu-item index="task">
          <el-icon><Operation /></el-icon>
          <span>任务看板</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-spacer"></div>

      <div class="sidebar-bottom">
        <el-menu :default-active="activeTab" class="nav-menu" @select="selectTab">
          <el-menu-item index="account">
            <el-icon><User /></el-icon>
            <span>账号管理</span>
          </el-menu-item>
        </el-menu>
      </div>
    </el-aside>

    <el-container class="main-area">
      <el-header class="topbar">
        <div>
          <p>工作台</p>
          <h1>{{ tabSubtitle }}</h1>
        </div>
        <el-tag effect="dark" type="success">系统就绪</el-tag>
      </el-header>

      <el-main v-if="activeTab === 'account'" class="account-workspace">
        <AccountView />
      </el-main>

      <el-main v-else-if="activeTab === 'confirm'" class="confirm-workspace">
        <PublishConfirmView
          :selected-platforms="selectedPlatforms"
          :loading="taskLoading"
          :validation-report="validationReport"
          @back="activeTab = 'preview'"
          @submit="submitPublish"
        />
      </el-main>

      <el-main v-else-if="activeTab === 'task'" class="task-workspace">
        <TaskView
          :tasks="tasks"
          :loading="taskLoading || taskHistoryLoading"
          :error-message="errorMessage"
          :action-loading="taskActionLoading"
          @refresh-tasks="loadPublishTasks(true)"
          @refresh-task="refreshTaskStatus"
          @publish-draft="publishDraftFromTask"
        />
      </el-main>

      <el-main v-else class="workspace">
        <EditorView
          v-model:title="title"
          v-model:content="content"
          v-model:tags="tags"
          v-model:platforms="selectedPlatforms"
          v-model:assets="editorAssets"
          :word-count="wordCount"
          :preview-loading="previewLoading"
          :agent-loading="agentLoading"
          :has-preview="Boolean(preview)"
          :platform-drafts="preview?.drafts ?? {}"
          @generate-preview="generatePreview"
          @optimize-all-with-agent="optimizeAllWithAgent"
          @optimize-with-agent="optimizeWithAgent"
          @update-platform-draft="updatePlatformDraft"
          @open-preview="openPreviewDialog"
          @confirm-publish="enterPublishConfirm"
        />
      </el-main>
    </el-container>

    <!-- 预览弹窗 -->
    <el-dialog
      v-model="previewDialogVisible"
      width="90%"
      top="5vh"
      destroy-on-close
      class="preview-dialog"
    >
      <template #header>
        <span class="dialog-title">多平台内容预览</span>
      </template>

      <div class="preview-dialog-body">
        <PreviewView
          :initial-platform="previewDialogPlatform"
          :drafts="drafts"
          :loading="previewLoading"
          :error-message="errorMessage"
          :preview-id="preview?.preview_id ?? ''"
          :created-at="preview?.created_at ?? ''"
          @confirm-publish="enterPublishConfirm"
        />

        <el-collapse v-model="publishFormExpanded" class="publish-form-collapse">
          <el-collapse-item name="publish-params">
            <template #title>
              <span class="collapse-title-row">
                <el-icon class="collapse-arrow">
                  <ArrowDown v-if="publishFormExpanded.includes('publish-params')" />
                  <ArrowRight v-else />
                </el-icon>
                <span>发布参数（可选调整）</span>
              </span>
            </template>
            <PublishFormView
              v-model:forms="publishForms"
              :selected-platforms="selectedPlatforms"
              :validation-report="validationReport"
              :assets="editorAssets"
            />
          </el-collapse-item>
        </el-collapse>

        <!-- 发布确认按钮 — 置于真实发布参数下方 -->
        <div v-if="preview?.preview_id" class="preview-dialog-footer">
          <div class="dialog-notice">
            <el-icon><WarningFilled /></el-icon>
            <span>预览编号：{{ preview.preview_id }}<template v-if="preview.created_at">，创建时间：{{ preview.created_at }}</template></span>
          </div>

          <el-button
            type="primary"
            size="large"
            :icon="Right"
            @click="enterPublishConfirm"
          >
            进入发布确认
          </el-button>
        </div>
      </div>
    </el-dialog>
  </el-container>
</template>

<style scoped>
:global(body) {
  margin: 0;
  min-width: 320px;
  background: #f3f5f8;
  color: #172033;
  font-family:
    Inter, "PingFang SC", "Microsoft YaHei", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

:global(#app) {
  min-height: 100vh;
}

.app-shell {
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #172033;
  color: #f7fafc;
  padding: 24px 14px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 8px 26px;
  flex-shrink: 0;
}

.brand strong,
.brand span {
  display: block;
}

.brand strong {
  font-size: 18px;
}

.brand span {
  margin-top: 4px;
  color: #aab6c7;
  font-size: 13px;
}

.nav-menu {
  border-right: 0;
  background: transparent;
  flex-shrink: 0;
}

.nav-menu :deep(.el-menu-item) {
  color: #c6d2e1;
  border-radius: 8px;
}

.nav-menu :deep(.el-menu-item.is-active),
.nav-menu :deep(.el-menu-item:hover) {
  background: #263347;
  color: #ffffff;
}

.sidebar-spacer {
  flex: 1;
}

.sidebar-bottom {
  flex-shrink: 0;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.main-area {
  height: 100vh;
  overflow-y: auto;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: auto;
  min-height: 96px;
  padding: 24px 32px;
  background: #ffffff;
  border-bottom: 1px solid #dfe5ee;
}

.topbar p,
.topbar h1 {
  margin: 0;
}

.topbar p {
  color: #607086;
  font-size: 13px;
}

.topbar h1 {
  margin-top: 6px;
  font-size: 22px;
  font-weight: 650;
}

.workspace {
  padding: 24px 32px 32px;
}

.account-workspace,
.confirm-workspace,
.task-workspace {
  padding: 24px 32px 32px;
}

/* ---------- 预览弹窗 ---------- */
.preview-dialog :deep(.el-dialog__header) {
  padding: 20px 24px 0;
}

.dialog-title {
  font-size: 18px;
  font-weight: 650;
  color: #172033;
}

.preview-dialog :deep(.el-dialog__body) {
  padding: 8px 24px 24px;
}

.preview-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.publish-form-collapse {
  border: 1px solid #e8ecf2;
  border-radius: 8px;
  overflow: hidden;
}

.publish-form-collapse :deep(.el-collapse-item__header) {
  padding: 0 16px;
  font-weight: 500;
  color: #607086;
  background: #f7f9fb;
  border-bottom: none;
}

.publish-form-collapse :deep(.el-collapse-item__arrow) {
  display: none;
}

.collapse-title-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.collapse-arrow {
  font-size: 14px;
  color: #9aa9bb;
  transition: transform 0.2s ease;
}

.publish-form-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.publish-form-collapse :deep(.el-collapse-item__content) {
  padding-bottom: 16px;
}

.preview-dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-top: 16px;
  border-top: 1px solid #e8ecf2;
}

.dialog-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #4f6279;
  font-size: 13px;
  word-break: break-all;
  min-width: 0;
}

@media (max-width: 960px) {
  .app-shell {
    display: block;
    height: auto;
    overflow: visible;
  }

  .sidebar {
    width: auto !important;
    height: auto;
    padding: 16px;
  }

  .brand {
    padding-bottom: 14px;
  }

  .sidebar-spacer {
    display: none;
  }

  .sidebar-bottom {
    border-top: none;
    padding-top: 0;
  }

  .main-area {
    height: auto;
    overflow-y: visible;
  }

  .topbar {
    align-items: flex-start;
    gap: 16px;
    padding: 20px;
  }

  .workspace,
  .account-workspace,
  .confirm-workspace,
  .task-workspace {
    padding: 20px;
  }

  .preview-dialog-footer {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
