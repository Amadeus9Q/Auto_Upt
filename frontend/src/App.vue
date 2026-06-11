<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Expand, Fold, FolderOpened, Monitor, Operation, Right, User, VideoPlay, WarningFilled } from "@element-plus/icons-vue";

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
  type AgentWritingStyle,
  type AssetPayload,
  type ContentPayload,
  type ContentBlockPayload,
  type DraftPayload,
  type PlatformKey,
  type PreviewDraftUpdatePayload,
  type PreviewResponse,
  type ValidationIssue,
  type PublishMode,
  type PublishTaskCreatePayload,
  type PublishTaskResponse
} from "@/api/client";
import AccountView from "@/views/AccountView.vue";
import EditorView from "@/views/EditorView.vue";
import MediaLibraryView from "@/views/MediaLibraryView.vue";
import PreviewView, { type PlatformDraft } from "@/views/PreviewView.vue";
import PublishConfirmView from "@/views/PublishConfirmView.vue";
import { type PublishForms } from "@/views/PublishFormView.vue";
import TaskView from "@/views/TaskView.vue";
import type { EditorAssets, LocalAsset, MediaFolder, MediaTab } from "@/types/media";

import {
  getErrorMessage,
  parseTagText,
  PLATFORM_AGENT_STYLE_GOALS,
  PLATFORM_LABELS,
  REAL_PUBLISH_PLATFORMS,
  STORAGE_KEYS,
} from "@/utils";
import { useDebounce } from "@/composables/useDebounce";
import { useIndexedDB } from "@/composables/useIndexedDB";
import { ASSET_MARKER_PATTERN } from "@/utils/assetMarkers";

type WorkspaceTab = "preview" | "task" | "media" | "account";
type ContentWorkflowStage = 1 | 2 | 3;
type TaskStep = {
  name: string;
  state: "wait" | "process" | "finish" | "error" | "success";
};
type AgentOptimizeOptions = {
  updateTitle: boolean;
  updateTags: boolean;
  writingStyle: AgentWritingStyle;
  customWritingStyle?: string | null;
};

const activeTab = ref<WorkspaceTab>("preview");
const activeContentStage = ref<ContentWorkflowStage>(1);
const sidebarCollapsed = ref(false);
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
const mediaFolders = ref<MediaFolder[]>([]);
const allAssets = computed(() => [...editorAssets.value.images, ...editorAssets.value.videos, ...editorAssets.value.audios]);
const publishForms = ref<PublishForms>({
  bilibili: {
    title: "",
    description: "",
    tags: "",
    category: ""
  },
  wechat: {
    title: "",
    summary: "",
    author: "",
    contentSourceUrl: "",
    needOpenComment: false,
    onlyFansCanComment: false,
    directPublish: false
  },
  xiaohongshu: {
    title: "",
    content: ""
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
const taskErrorMessage = ref("");
const previewDialogVisible = ref(false);
const previewDialogPlatform = ref<PlatformKey>("wechat");
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
    preview: ["统一内容编译", "编辑所选平台", "发布确认"][activeContentStage.value - 1] ?? "内容工作流",
    task: "任务看板",
    media: "多媒体库",
    account: "账号管理"
  };
  return subtitles[activeTab.value] ?? "内容预览";
});

const contentWorkflowSteps: Array<{ stage: ContentWorkflowStage; title: string; description: string }> = [
  { stage: 1, title: "统一内容编译", description: "编辑正文、素材并选择平台" },
  { stage: 2, title: "编辑所选平台", description: "调整平台内容与预览" },
  { stage: 3, title: "发布确认", description: "检查并提交发布" }
];

const editorWorkflowStage = computed<1 | 2>(() => Math.min(activeContentStage.value, 2) as 1 | 2);
function hasDraftContent(draft?: DraftPayload | null) {
  return Boolean(draft?.title?.trim() || draft?.body?.trim() || (draft?.tags?.length ?? 0) > 0);
}
const hasGeneratedDraft = computed(() => {
  const platformDrafts = preview.value?.drafts ?? {};
  return Object.values(platformDrafts).some((draft) => hasDraftContent(draft));
});
const availableContentStage = computed<ContentWorkflowStage>(
  () => hasGeneratedDraft.value ? 3 : 1
);

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
      label: PLATFORM_LABELS[platform],
      title: draft?.title ?? PLATFORM_LABELS[platform],
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
  const middleStep = task.value?.mode === "draft" ? "保存到平台草稿箱" : task.value?.mode === "simulate" ? "检查发布准备" : "提交到平台";
  const finalStep = task.value?.mode === "draft" ? "已保存为草稿" : task.value?.mode === "simulate" ? "检查完成" : "已发布";

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

const { readAll: readStoredAssets, writeAll: writeStoredAssets } = useIndexedDB<StoredAssetRecord>(
  STORAGE_KEYS.MEDIA_LIBRARY_DB,
  STORAGE_KEYS.MEDIA_LIBRARY_STORE
);

type StoredAssetRecord = Omit<LocalAsset, "previewUrl" | "file"> & { file: File };
let mediaPersistTimer: number | null = null;
let mediaHydrated = false;

function assetsToStoredRecords(): StoredAssetRecord[] {
  return (["images", "videos", "audios"] as MediaTab[]).flatMap((tab) =>
    editorAssets.value[tab].map((asset) => ({
      id: asset.id,
      name: asset.name,
      size: asset.size,
      mimeType: asset.mimeType,
      kind: asset.kind,
      folderId: asset.folderId,
      aliasPaths: asset.aliasPaths,
      backendAssetId: asset.backendAssetId,
      backendUrl: asset.backendUrl,
      uploadPurpose: asset.uploadPurpose,
      file: asset.file
    }))
  );
}

async function hydrateMediaLibrary() {
  localStorage.removeItem(STORAGE_KEYS.COVER_IMAGE_ID);
  const storedFolders = localStorage.getItem(STORAGE_KEYS.MEDIA_FOLDERS);
  if (storedFolders) {
    try {
      mediaFolders.value = JSON.parse(storedFolders) as MediaFolder[];
    } catch {
      mediaFolders.value = [];
    }
  }

  try {
    const records = await readStoredAssets();
    const nextAssets: EditorAssets = { images: [], videos: [], audios: [], coverImage: null, coverImageId: null };
    for (const record of records) {
      const asset: LocalAsset = {
        ...record,
        previewUrl: URL.createObjectURL(record.file),
        file: record.file
      };
      const tab: MediaTab = asset.kind === "image" ? "images" : asset.kind === "video" ? "videos" : "audios";
      nextAssets[tab].push(asset);
    }
    editorAssets.value = nextAssets;
  } catch (error) {
    console.warn("[MediaLibrary] 恢复本地素材失败", error);
  } finally {
    mediaHydrated = true;
  }
}

function scheduleMediaLibraryPersist() {
  if (!mediaHydrated) return;
  if (mediaPersistTimer) window.clearTimeout(mediaPersistTimer);
  mediaPersistTimer = window.setTimeout(() => {
    localStorage.setItem(STORAGE_KEYS.MEDIA_FOLDERS, JSON.stringify(mediaFolders.value));
    localStorage.removeItem(STORAGE_KEYS.COVER_IMAGE_ID);
    void writeStoredAssets(assetsToStoredRecords()).catch((error) => {
      console.warn("[MediaLibrary] 保存本地素材失败", error);
    });
  }, 250);
}

watch(editorAssets, scheduleMediaLibraryPersist, { deep: true });
watch(mediaFolders, scheduleMediaLibraryPersist, { deep: true });

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

function assetFolderPath(asset: LocalAsset) {
  const names: string[] = [];
  let cursor = asset.folderId;
  while (cursor) {
    const folder = mediaFolders.value.find((item) => item.id === cursor);
    if (!folder) break;
    names.unshift(folder.name);
    cursor = folder.parentId ?? undefined;
  }
  return [...names, asset.name].join("/");
}

function collectAssetPayloads(sourceBody = content.value): AssetPayload[] {
  // Collect asset IDs referenced in the body via markers like 【图片：name】 or {{asset:image:id}}
  const referencedIds = new Set<string>();
  const markerPattern = /\{\{asset:(?:image|video|audio):([^}]+)\}\}|【(?:图片|视频|音频)：([^】]+)】/g;
  let match: RegExpExecArray | null;
  while ((match = markerPattern.exec(sourceBody)) !== null) {
    const displayToken = match[2]?.split("｜id:") ?? [];
    const idOrName = match[1] || displayToken[1] || displayToken[0];
    // Try to match by ID first, then by name
    const byId = allAssets.value.find((a) => a.id === idOrName);
    if (byId) { referencedIds.add(byId.id); continue; }
    const byName = allAssets.value.find((a) => a.name === idOrName || assetFolderPath(a) === idOrName);
    if (byName) referencedIds.add(byName.id);
  }

  const coverImage = editorAssets.value.coverImage
    ?? editorAssets.value.images.find((asset) => asset.id === editorAssets.value.coverImageId)
    ?? null;
  const coverImageId = coverImage?.id ?? null;
  if (coverImage) referencedIds.add(coverImage.id);

  return [
    ...editorAssets.value.images
      .filter((asset) => referencedIds.has(asset.id))
      .map((asset) => assetToPayload(asset, "image", asset.id === coverImageId ? "default_cover" : "body_image")),
    ...editorAssets.value.videos
      .filter((asset) => referencedIds.has(asset.id))
      .map((asset, index) => assetToPayload(asset, "video", index === 0 ? "bilibili_video" : "reference_video")),
    ...editorAssets.value.audios
      .filter((asset) => referencedIds.has(asset.id))
      .map((asset) => assetToPayload(asset, "audio", "reference_audio"))
  ];
}

function collectContentBlocks(sourceBody = content.value): ContentBlockPayload[] {
  const assetMap = new Map<string, LocalAsset>();
  const assetByDisplayToken = new Map<string, LocalAsset>();
  for (const asset of [...editorAssets.value.images, ...editorAssets.value.videos, ...editorAssets.value.audios]) {
    assetMap.set(asset.id, asset);
    const kindLabel = asset.kind === "image" ? "图片" : asset.kind === "video" ? "视频" : "音频";
    assetByDisplayToken.set(`${kindLabel}:${assetFolderPath(asset)}`, asset);
    if (!asset.folderId) {
      assetByDisplayToken.set(`${kindLabel}:${asset.name}`, asset);
    }
  }

  const blocks: ContentBlockPayload[] = [];
  const markerPattern = /\{\{asset:(image|video|audio):([^}]+)\}\}|【(图片|视频|音频)：([^】]+)】/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = markerPattern.exec(sourceBody)) !== null) {
    const text = sourceBody.slice(cursor, match.index).trim();
    if (text) {
      blocks.push({ type: "text", text });
    }

    const displayToken = match[4]?.split("｜id:") ?? [];
    const asset = match[1]
      ? assetMap.get(match[2])
      : assetMap.get(displayToken[1] ?? "") ?? assetByDisplayToken.get(`${match[3]}:${displayToken[0]}`);
    if (asset) {
      blocks.push({ type: "asset", asset_id: asset.id, asset_kind: asset.kind, role: "inline" });
    }
    cursor = match.index + match[0].length;
  }

  const trailingText = sourceBody.slice(cursor).trim();
  if (trailingText) {
    blocks.push({ type: "text", text: trailingText });
  }

  if (!blocks.length && sourceBody.trim()) {
    blocks.push({ type: "text", text: sourceBody.trim() });
  }

  return blocks;
}

function buildContentPayload(overrides: Partial<Pick<ContentPayload, "title" | "body" | "tags" | "platforms">> = {}): ContentPayload {
  const payloadBody = overrides.body ?? content.value;
  const payloadTags = overrides.tags ?? tagList.value;
  return {
    title: overrides.title ?? (title.value.trim() || undefined),
    body: payloadBody,
    content_type: editorAssets.value.videos.length ? "video" : collectAssetPayloads(payloadBody).length ? "mixed" : "article",
    tags: payloadTags,
    assets: collectAssetPayloads(payloadBody),
    content_blocks: collectContentBlocks(payloadBody),
    cover_asset_id: editorAssets.value.coverImage?.id ?? editorAssets.value.coverImageId ?? null,
    platforms: overrides.platforms ?? selectedPlatforms.value
  };
}

function normalizeAgentOptimizeOptions(options?: AgentOptimizeOptions): AgentOptimizeOptions {
  return {
    updateTitle: options?.updateTitle ?? false,
    updateTags: options?.updateTags ?? false,
    writingStyle: options?.writingStyle ?? "default",
    customWritingStyle: options?.customWritingStyle?.trim() || null
  };
}

function buildAgentMetadataPayload(
  basePayload: ContentPayload,
  options: AgentOptimizeOptions
) {
  return {
    title: basePayload.title,
    tags: basePayload.tags,
    update_title: options.updateTitle,
    update_tags: options.updateTags,
    writing_style: options.writingStyle,
    custom_writing_style: options.writingStyle === "custom" ? options.customWritingStyle ?? null : null
  };
}

function preserveAssetMarkers(sourceBody: string, generatedBody: string) {
  const collectMarkers = (body: string) => {
    const pattern = new RegExp(ASSET_MARKER_PATTERN.source, "g");
    return Array.from(body.matchAll(pattern), (match) => match[0]);
  };
  const generatedMarkers = new Set(collectMarkers(generatedBody));
  const missingMarkers = collectMarkers(sourceBody).filter((marker) => !generatedMarkers.has(marker));
  if (!missingMarkers.length) {
    return generatedBody;
  }
  return `${generatedBody.trim()}\n\n${missingMarkers.join("\n\n")}`.trim();
}

function agentDraftPayloadForPlatform(
  run: Awaited<ReturnType<typeof runAgentAdaptPreview>>,
  platform: PlatformKey,
  options: AgentOptimizeOptions
): ContentPayload {
  const generatedDraft = run.drafts[platform];
  const generated = generatedDraft
    ? {
        title: generatedDraft.title,
        body: generatedDraft.body,
        tags: generatedDraft.tags
      }
    : {
        title: run.rewritten_content.title,
        body: run.rewritten_content.body,
        tags: run.rewritten_content.tags
      };

  return buildContentPayload({
    title: options.updateTitle || !title.value.trim() ? generated.title : title.value.trim(),
    body: preserveAssetMarkers(content.value, generated.body),
    tags: options.updateTags || !tagList.value.length ? generated.tags : tagList.value,
    platforms: [platform]
  });
}

function mergePreviewResponses(
  responses: PreviewResponse[],
  previousDrafts: Partial<Record<PlatformKey, DraftPayload>>,
  previousValidation: Partial<Record<PlatformKey, ValidationIssue[]>>
): PreviewResponse | null {
  const latest = responses[responses.length - 1];
  if (!latest) {
    return null;
  }

  return {
    ...latest,
    drafts: responses.reduce<Partial<Record<PlatformKey, DraftPayload>>>(
      (draftMap, response) => ({ ...draftMap, ...response.drafts }),
      { ...previousDrafts }
    ),
    validation_report: responses.reduce<Partial<Record<PlatformKey, ValidationIssue[]>>>(
      (validationMap, response) => ({ ...validationMap, ...response.validation_report }),
      { ...previousValidation }
    )
  };
}

async function optimizePlatformDraft(
  platform: PlatformKey,
  options: AgentOptimizeOptions,
  previewId: string | null
): Promise<PreviewResponse> {
  const basePayload = buildContentPayload({ platforms: [platform] });
  const run = await runAgentAdaptPreview({
    ...basePayload,
    ...buildAgentMetadataPayload(basePayload, options),
    preview_id: previewId,
    body: basePayload.body,
    platforms: [platform],
    style_goal: PLATFORM_AGENT_STYLE_GOALS[platform],
    rewrite_strength: "medium",
    use_llm: "auto",
    persist_preview: false
  });

  return createPreview(agentDraftPayloadForPlatform(run, platform, options));
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
      const message = getErrorMessage(error, "同步平台内容失败，请检查网络连接。");
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
        ...patch,
        ...(patch.body !== undefined
          ? {
              body_blocks: [],
              rich_body: [],
              content_points: [],
              highlights: [],
              wechat_html: ""
            }
          : {})
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
    account_ids: {},
    asset_ids: {},
    platform_options: {},
    results: Object.fromEntries(
      platforms.map((platform) => [
        platform,
        {
          platform,
          display_name: PLATFORM_LABELS[platform],
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
  return editorAssets.value.coverImage ?? editorAssets.value.images.find((image) => image.id === editorAssets.value.coverImageId) ?? null;
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
  if (!asset.uploadPurpose) {
    asset.uploadPurpose = purpose;
  }
  return uploaded.asset_id;
}

function referencedPlatformImages(platform: PlatformKey): LocalAsset[] {
  const referencedIds = new Set<string>();
  for (const block of preview.value?.drafts[platform]?.body_blocks ?? []) {
    if (block.type === "asset" && block.asset_kind === "image" && block.asset?.id) {
      referencedIds.add(block.asset.id);
    }
  }

  if (!referencedIds.size) {
    for (const asset of collectAssetPayloads(content.value)) {
      if (asset.type === "image" || asset.type === "body_image") {
        referencedIds.add(asset.id);
      }
    }
  }
  return editorAssets.value.images.filter((image) => referencedIds.has(image.id));
}

async function preparePlatformImages(
  platform: "wechat" | "xiaohongshu",
  cover: LocalAsset,
): Promise<{ coverAssetId: string; assetIds: string[] }> {
  const purposePrefix = platform === "wechat" ? "wechat" : "xiaohongshu";
  const images = [...new Map([cover, ...referencedPlatformImages(platform)].map((image) => [image.id, image])).values()];
  const uploaded = await Promise.all(
    images.map(async (image) => ({
      image,
      assetId: await ensureBackendAsset(
        image,
        image.id === cover.id ? `${purposePrefix}_cover` : `${purposePrefix}_body_image`,
      ),
    })),
  );
  return {
    coverAssetId: uploaded.find(({ image }) => image.id === cover.id)!.assetId,
    assetIds: uploaded.map(({ assetId }) => assetId),
  };
}

async function resolveConnectedAccountIds(platforms: PlatformKey[]): Promise<Partial<Record<PlatformKey, string>>> {
  const accounts = await getAccounts();
  const accountIds: Partial<Record<PlatformKey, string>> = {};

  for (const platform of platforms) {
    const account = accounts.find((item) => item.platform === platform && item.status === "connected" && item.account_id);
    if (!account?.account_id) {
      throw new Error(`请先在「账号管理」中连接${PLATFORM_LABELS[platform]}账号，再执行发布操作。`);
    }
    accountIds[platform] = account.account_id;
  }

  return accountIds;
}

function buildPlatformOptions(platforms: PlatformKey[], forms: PublishForms): NonNullable<PublishTaskCreatePayload["platform_options"]> {
  const platformOptions: NonNullable<PublishTaskCreatePayload["platform_options"]> = {};

  if (platforms.includes("wechat")) {
    const wechatDraft = preview.value?.drafts.wechat;
    platformOptions.wechat = {
      title: forms.wechat.title.trim() || wechatDraft?.title || "",
      author: forms.wechat.author.trim(),
      digest: forms.wechat.summary.trim() || wechatDraft?.summary || wechatDraft?.body?.slice(0, 120) || "",
      content_source_url: forms.wechat.contentSourceUrl.trim(),
      need_open_comment: forms.wechat.needOpenComment,
      only_fans_can_comment: forms.wechat.needOpenComment && forms.wechat.onlyFansCanComment,
      direct_publish: forms.wechat.directPublish
    };
  }

  if (platforms.includes("bilibili")) {
    const bilibiliDraft = preview.value?.drafts.bilibili;
    platformOptions.bilibili = {
      title: forms.bilibili.title.trim() || bilibiliDraft?.title || "",
      description: forms.bilibili.description.trim() || bilibiliDraft?.body || "",
      tags: parseTagText(forms.bilibili.tags).length
        ? parseTagText(forms.bilibili.tags)
        : bilibiliDraft?.tags ?? [],
      tid: Number(forms.bilibili.category) || 201,
      copyright: 1,
      source: "",
      no_reprint: true,
      dynamic: ""
    };
  }

  if (platforms.includes("xiaohongshu")) {
    const xhsDraft = preview.value?.drafts.xiaohongshu;
    platformOptions.xiaohongshu = {
      title: forms.xiaohongshu.title.trim() || xhsDraft?.title || "",
      content: forms.xiaohongshu.content.trim() || xhsDraft?.body || "",
    };
  }

  return platformOptions;
}

async function buildPublishTaskPayload(payload: { platforms: PlatformKey[]; mode: PublishMode; useUnifiedSettings: boolean; forms: PublishForms }): Promise<PublishTaskCreatePayload> {
  if (!preview.value) {
    throw new Error("请先生成草稿。");
  }

  const platformOptions = buildPlatformOptions(payload.platforms, payload.forms);

  if (payload.mode === "simulate") {
    return {
      preview_id: preview.value.preview_id,
      mode: payload.mode,
      platforms: payload.platforms,
      platform_options: platformOptions,
      inline_drafts: preview.value.drafts,
      inline_content_ir: preview.value.content_ir
    };
  }

  const platforms = payload.platforms.filter((platform) => REAL_PUBLISH_PLATFORMS.includes(platform));
  if (!platforms.length) {
    throw new Error("当前版本只有公众号、B站和小红书支持保存草稿或真实发布。");
  }
  if (platforms.length !== payload.platforms.length) {
    throw new Error("知乎当前只能查看模拟结果，暂不能直接发布。");
  }

  const accountIds = await resolveConnectedAccountIds(platforms);
  const assetIds: NonNullable<PublishTaskCreatePayload["asset_ids"]> = {};

  if (platforms.includes("wechat")) {
    const cover = getCoverImage();
    if (!cover) {
      throw new Error("公众号发布需要先上传封面图。");
    }

    const prepared = await preparePlatformImages("wechat", cover);
    assetIds.wechat = prepared.assetIds;
    platformOptions.wechat = {
      ...(platformOptions.wechat ?? {}),
      cover_asset_id: prepared.coverAssetId,
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

    platformOptions.bilibili = {
      ...(platformOptions.bilibili ?? {}),
      video_asset_id: videoAssetId,
      cover_asset_id: coverAssetId,
    };
  }

  if (platforms.includes("xiaohongshu")) {
    const cover = getCoverImage();
    if (!cover) {
      throw new Error("小红书发布需要先上传封面图。");
    }

    const prepared = await preparePlatformImages("xiaohongshu", cover);
    const xhsAssetIds = new Set<string>(prepared.assetIds);

    // 视频笔记：需要视频素材
    const video = editorAssets.value.videos[0] ?? null;
    if (video) {
      xhsAssetIds.add(await ensureBackendAsset(video, "xiaohongshu_video"));
    }

    assetIds.xiaohongshu = [...xhsAssetIds];
    platformOptions.xiaohongshu = {
      ...(platformOptions.xiaohongshu ?? {}),
      cover_asset_id: prepared.coverAssetId,
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
    taskErrorMessage.value = "";
    if (showToast) {
      ElMessage.success("任务列表已刷新。");
    }
  } catch (error) {
    const message = getErrorMessage(error, "加载任务列表失败。");
    taskErrorMessage.value = showToast || tasks.value.length > 0 ? message : "";
    if (showToast) {
      ElMessage.error(message);
    } else {
      console.warn("[TaskBoard] 初始任务列表加载失败", error);
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
    taskErrorMessage.value = "";
    ElMessage.success("任务状态已更新。");
  } catch (error) {
    const message = getErrorMessage(error, "更新任务状态失败。");
    taskErrorMessage.value = message;
    ElMessage.error(message);
  } finally {
    taskActionLoading.value = null;
  }
}

async function publishDraftFromTask(publicationId: string) {
  try {
    await ElMessageBox.confirm("确认把这份内容提交到平台？提交后系统会开始执行发布流程。", "确认发布", {
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
    taskErrorMessage.value = "";
    ElMessage.success("内容已加入发布队列。");
  } catch (error) {
    const message = getErrorMessage(error, "提交发布请求失败。");
    taskErrorMessage.value = message;
    ElMessage.error(message);
  } finally {
    taskActionLoading.value = null;
  }
}

async function generatePreview() {
  if (previewLoading.value || !content.value.trim()) {
    return;
  }

  const existingDraftPlatforms = selectedPlatforms.value.filter((platform) => hasDraftContent(preview.value?.drafts[platform]));
  previewLoading.value = true;
  if (existingDraftPlatforms.length) {
    try {
      await ElMessageBox.confirm("生成草稿会覆盖已有平台草稿，是否继续？", "确认生成草稿", {
        confirmButtonText: "确认",
        cancelButtonText: "取消",
        type: "warning"
      });
    } catch {
      previewLoading.value = false;
      return;
    }
  }

  // 记录调用前标题和关键词是否为空，用于回填判断
  const titleWasEmpty = !title.value.trim();
  const tagsWereEmpty = !tags.value.trim();

  // 获取已有的平台草稿和校验报告
  const previousDrafts = preview.value?.drafts ?? {} as Partial<Record<PlatformKey, DraftPayload>>;
  const previousValidation = preview.value?.validation_report ?? {} as Partial<Record<PlatformKey, ValidationIssue[]>>;
  const payload = buildContentPayload({ platforms: [...selectedPlatforms.value] });

  errorMessage.value = "";
  task.value = null;

  try {
    const response = await createPreview(payload);
    const mergedPreview = mergePreviewResponses([response], previousDrafts, previousValidation);
    if (!mergedPreview) return;
    preview.value = mergedPreview;

    // 回填：如果调用前标题为空且后端生成了标题，自动填入
    const ir = response.content_ir as Record<string, unknown> | null | undefined;
    if (titleWasEmpty && ir) {
      const generatedTitle = ir["title"];
      if (typeof generatedTitle === "string" && generatedTitle.trim() && generatedTitle !== "Untitled Content") {
        title.value = generatedTitle;
      }
    }
    // 回填：如果调用前关键词为空且后端生成了关键词，自动填入
    if (tagsWereEmpty && ir) {
      const generatedTags = ir["tags"];
      if (Array.isArray(generatedTags) && generatedTags.length > 0 && generatedTags.every((t: unknown) => typeof t === "string")) {
        tags.value = (generatedTags as string[]).join(", ");
      }
    }

    ElMessage.success("草稿已生成。");
    activeContentStage.value = 2;
  } catch (error) {
    errorMessage.value = getErrorMessage(error, "草稿生成失败，请稍后重试。");
    ElMessage.error(errorMessage.value);
  } finally {
    previewLoading.value = false;
  }
}

function clearPlatformDraft(platform: PlatformKey) {
  if (!preview.value) return;
  const currentDraft = preview.value.drafts[platform];
  if (!currentDraft) return;
  updatePlatformDraft(platform, { title: "", body: "", tags: [] });
  // 如果清除后所有平台草稿都为空，重置预览状态
  const allCleared = Object.values(preview.value.drafts).every(
    d => !d?.body?.trim()
  );
  if (allCleared) {
    preview.value = null;
  }
}

function clearCheckedPlatformDrafts() {
  if (!preview.value) return;
  for (const platform of selectedPlatforms.value) {
    clearPlatformDraft(platform);
  }
  // 如果清除后所有平台草稿都为空，重置预览状态
  const allCleared = Object.values(preview.value.drafts).every(
    d => !d?.body?.trim()
  );
  if (allCleared) {
    preview.value = null;
  }
}

function clearBasicInfo() {
  title.value = "";
  tags.value = "";
}

function clearContent() {
  content.value = "";
  preview.value = null;
}

async function optimizeAllWithAgent(rawOptions?: AgentOptimizeOptions) {
  if (!content.value.trim()) {
    ElMessage.warning("请先输入正文内容。");
    return;
  }
  if (!selectedPlatforms.value.length) {
    ElMessage.warning("请至少选择一个平台。");
    return;
  }

  const options = normalizeAgentOptimizeOptions(rawOptions);
  const targetPlatforms = [...selectedPlatforms.value];
  agentLoading.value = true;
  errorMessage.value = "";

  try {
    const previousDrafts = preview.value?.drafts ?? {} as Partial<Record<PlatformKey, DraftPayload>>;
    const previousValidation = preview.value?.validation_report ?? {} as Partial<Record<PlatformKey, ValidationIssue[]>>;
    const previewId = preview.value?.preview_id ?? null;
    const responses: PreviewResponse[] = [];
    for (const platform of targetPlatforms) {
      responses.push(await optimizePlatformDraft(platform, options, previewId));
    }
    const mergedPreview = mergePreviewResponses(responses, previousDrafts, previousValidation);
    if (mergedPreview) preview.value = mergedPreview;
    ElMessage.success("所选平台的智能优化结果已生成。");
  } catch (error) {
    const message = getErrorMessage(error, "智能优化失败。");
    errorMessage.value = message;
    ElMessage.error(message);
  } finally {
    agentLoading.value = false;
  }
}

async function optimizeWithAgent(platform: PlatformKey, rawOptions?: AgentOptimizeOptions) {
  if (!content.value.trim()) {
    ElMessage.warning("请先输入正文内容。");
    return;
  }
  if (!preview.value) {
    ElMessage.warning("请先生成草稿，再优化当前平台内容。");
    return;
  }

  const options = normalizeAgentOptimizeOptions(rawOptions);
  agentLoading.value = true;
  errorMessage.value = "";

  try {
    const response = await optimizePlatformDraft(platform, options, preview.value.preview_id);
    const mergedPreview = mergePreviewResponses(
      [response],
      preview.value.drafts,
      preview.value.validation_report
    );
    if (mergedPreview) preview.value = mergedPreview;
    ElMessage.success(`${PLATFORM_LABELS[platform]}内容已优化。`);
  } catch (error) {
    const message = getErrorMessage(error, "智能优化失败。");
    errorMessage.value = message;
    ElMessage.error(message);
  } finally {
    agentLoading.value = false;
  }
}

function enterPublishConfirm() {
  if (!hasGeneratedDraft.value) {
    ElMessage.warning("请先生成草稿。");
    return;
  }
  previewDialogVisible.value = false;
  activeTab.value = "preview";
  activeContentStage.value = 3;
}

async function submitPublish(payload: { platforms: PlatformKey[]; mode: PublishMode; useUnifiedSettings: boolean; forms: PublishForms }) {
  if (!preview.value || !hasGeneratedDraft.value) {
    ElMessage.warning("请先生成草稿。");
    return;
  }

  if (payload.mode === "draft" || payload.mode === "publish") {
    try {
      await ElMessageBox.confirm(
        payload.mode === "publish"
          ? "确认后会调用真实平台接口提交发布。请确认账号、素材和平台规则已经检查无误。"
          : "确认后会把内容保存到平台草稿箱。请确认账号和素材已经检查无误。",
        "提交前确认",
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
  taskErrorMessage.value = "";
  activeTab.value = "task";

  try {
    upsertTask(await createPublishTask(await buildPublishTaskPayload(payload)));
    taskErrorMessage.value = "";
    ElMessage.success(payload.mode === "simulate" ? "模拟发布任务已创建。" : "发布任务已提交。");
  } catch (error) {
    const message = getErrorMessage(error, "创建发布任务失败。");
    const failedTask = createFailedLocalTask(preview.value.preview_id, payload.platforms, payload.mode, message);
    task.value = failedTask;
    tasks.value = [failedTask, ...tasks.value];
    taskErrorMessage.value = message;
    ElMessage.error("发布任务提交失败，已在任务看板展示原因。");
  } finally {
    taskLoading.value = false;
  }
}

function selectTab(key: string) {
  activeTab.value = key as WorkspaceTab;
}

function selectContentStage(stage: ContentWorkflowStage) {
  if (stage > activeContentStage.value) {
    if (stage <= availableContentStage.value) {
      activeContentStage.value = stage;
      return;
    }
    if (stage === 3) {
      ElMessage.warning("请先生成草稿。");
      return;
    }
    ElMessage.warning(
      hasGeneratedDraft.value
        ? "请先进入编辑所选平台。"
        : "请点击“选择生成平台”区域右侧的“生成草稿”按钮进入编辑所选平台。"
    );
    return;
  }
  activeContentStage.value = stage;
}

function openPreviewDialog(platform?: PlatformKey) {
  previewDialogPlatform.value = platform ?? "wechat";
  previewDialogVisible.value = true;
}

onMounted(async () => {
  await hydrateMediaLibrary();
  void loadPublishTasks(false);
});
</script>

<template>
  <el-container class="app-shell">
    <el-aside
      class="sidebar"
      :class="{ 'is-collapsed': sidebarCollapsed }"
      :width="sidebarCollapsed ? '76px' : '236px'"
    >
      <div class="brand">
        <el-icon :size="28"><VideoPlay /></el-icon>
        <div v-show="!sidebarCollapsed" class="brand-copy">
          <strong>Auto_Upt</strong>
          <span>内容发布助手</span>
        </div>
        <el-tooltip v-if="!sidebarCollapsed" content="折叠侧边栏" placement="right">
          <el-button
            class="sidebar-collapse-button"
            text
            circle
            :icon="Fold"
            aria-label="折叠侧边栏"
            @click="sidebarCollapsed = true"
          />
        </el-tooltip>
        <el-tooltip v-if="sidebarCollapsed" content="展开侧边栏" placement="right">
          <el-button
            class="sidebar-collapse-button"
            text
            circle
            :icon="Expand"
            aria-label="展开侧边栏"
            @click="sidebarCollapsed = false"
          />
        </el-tooltip>
      </div>

      <el-menu :default-active="activeTab" :collapse="sidebarCollapsed" class="nav-menu" @select="selectTab">
        <el-menu-item index="preview" :title="sidebarCollapsed ? '内容工作台' : undefined">
          <el-icon><Monitor /></el-icon>
          <span>内容工作台</span>
        </el-menu-item>
        <el-menu-item index="task" :title="sidebarCollapsed ? '任务看板' : undefined">
          <el-icon><Operation /></el-icon>
          <span>任务看板</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-spacer"></div>

      <div class="sidebar-bottom">
        <el-menu :default-active="activeTab" :collapse="sidebarCollapsed" class="nav-menu" @select="selectTab">
          <el-menu-item index="media" :title="sidebarCollapsed ? '多媒体库' : undefined">
            <el-icon><FolderOpened /></el-icon>
            <span>多媒体库</span>
          </el-menu-item>
          <el-menu-item index="account" :title="sidebarCollapsed ? '账号管理' : undefined">
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

      <el-main v-else-if="activeTab === 'media'" class="media-workspace">
        <MediaLibraryView
          v-model:assets="editorAssets"
          v-model:folders="mediaFolders"
        />
      </el-main>

      <el-main v-else-if="activeTab === 'task'" class="task-workspace">
        <TaskView
          :tasks="tasks"
          :loading="taskLoading || taskHistoryLoading"
          :error-message="taskErrorMessage"
          :action-loading="taskActionLoading"
          @refresh-tasks="loadPublishTasks(true)"
          @refresh-task="refreshTaskStatus"
          @publish-draft="publishDraftFromTask"
        />
      </el-main>

      <el-main v-else class="workspace">
        <nav class="content-workflow" aria-label="内容发布流程">
          <button
            v-for="step in contentWorkflowSteps"
            :key="step.stage"
            type="button"
            class="content-workflow-step"
            :class="{
              'is-active': activeContentStage === step.stage,
              'is-finished': activeContentStage > step.stage,
              'is-available': step.stage <= activeContentStage || step.stage <= availableContentStage
            }"
            :aria-current="activeContentStage === step.stage ? 'step' : undefined"
            @click="selectContentStage(step.stage)"
          >
            <span class="content-workflow-index">{{ step.stage }}</span>
            <span class="content-workflow-copy">
              <strong>{{ step.title }}</strong>
              <small>{{ step.description }}</small>
            </span>
          </button>
        </nav>

        <PublishConfirmView
          v-if="activeContentStage === 3"
          v-model:publish-forms="publishForms"
          :selected-platforms="selectedPlatforms"
          :loading="taskLoading"
          :validation-report="validationReport"
          :assets="editorAssets"
          :platform-drafts="preview?.drafts"
          @back="activeContentStage = 2"
          @submit="submitPublish"
        />

        <EditorView
          v-else
          v-model:title="title"
          v-model:content="content"
          v-model:tags="tags"
          v-model:platforms="selectedPlatforms"
          v-model:assets="editorAssets"
          v-model:media-folders="mediaFolders"
          :word-count="wordCount"
          :preview-loading="previewLoading"
          :agent-loading="agentLoading"
          :publish-loading="taskLoading"
          :has-preview="Boolean(preview)"
          :platform-drafts="preview?.drafts ?? {}"
          :validation-report="validationReport"
          :workflow-stage="editorWorkflowStage"
          @generate-preview="generatePreview"
          @optimize-all-with-agent="optimizeAllWithAgent"
          @optimize-with-agent="optimizeWithAgent"
          @update-platform-draft="updatePlatformDraft"
          @open-preview="openPreviewDialog"
          @clear-platform-draft="clearPlatformDraft"
          @clear-checked-platform-drafts="clearCheckedPlatformDrafts"
          @clear-basic-info="clearBasicInfo"
          @clear-content="clearContent"
          @confirm-publish="enterPublishConfirm"
        />
      </el-main>
    </el-container>

    <!-- 预览弹窗 -->
    <el-dialog
      v-model="previewDialogVisible"
      width="min(96vw, 1680px)"
      top="2vh"
      destroy-on-close
      :close-on-click-modal="false"
      :close-on-press-escape="true"
      show-close
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

      </div>

      <template #footer>
        <div class="preview-dialog-footer">
          <div class="dialog-notice">
            <el-icon><WarningFilled /></el-icon>
            <span>预览记录：{{ preview?.preview_id }}<template v-if="preview?.created_at">，创建时间：{{ preview.created_at }}</template></span>
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
      </template>
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
  transition:
    width 0.2s ease,
    padding 0.2s ease;
}

.sidebar.is-collapsed {
  padding-right: 10px;
  padding-left: 10px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 8px 26px;
  flex-shrink: 0;
}

.sidebar.is-collapsed .brand {
  display: grid;
  justify-content: center;
  gap: 12px;
  padding-right: 0;
  padding-left: 0;
}

.brand-copy {
  min-width: 0;
}

.sidebar-collapse-button {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  color: #aab6c7;
  background: rgba(255, 255, 255, 0.06);
}

.sidebar-collapse-button:hover {
  color: #ffffff;
  background: #263347;
}

.sidebar.is-collapsed .sidebar-collapse-button {
  justify-self: center;
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

.nav-menu.el-menu--collapse {
  width: 100%;
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

.sidebar.is-collapsed .nav-menu :deep(.el-menu-item) {
  justify-content: center;
  padding: 0 !important;
}

.sidebar.is-collapsed .nav-menu :deep(.el-menu-item .el-icon) {
  margin-right: 0;
}

.content-workflow {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}

.content-workflow-step {
  position: relative;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 12px;
  color: #8492a6;
  text-align: left;
  cursor: not-allowed;
  background: #f8fafc;
  border: 1px solid #dfe5ee;
  border-radius: 8px;
}

.content-workflow-step.is-available {
  color: #4f6279;
  cursor: pointer;
  background: #ffffff;
}

.content-workflow-step.is-active {
  color: #1f6feb;
  border-color: #1f6feb;
  box-shadow: 0 0 0 3px rgba(31, 111, 235, 0.1);
}

.content-workflow-step.is-finished {
  color: #2b7a4b;
  border-color: #a9d6bc;
}

.content-workflow-index {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  color: #ffffff;
  background: #9aa9bb;
  border-radius: 50%;
  font-weight: 700;
}

.content-workflow-step.is-active .content-workflow-index {
  background: #1f6feb;
}

.content-workflow-step.is-finished .content-workflow-index {
  background: #2b7a4b;
}

.content-workflow-copy {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.content-workflow-copy strong,
.content-workflow-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content-workflow-copy strong {
  font-size: 14px;
}

.content-workflow-copy small {
  font-size: 12px;
}

.account-workspace,
.confirm-workspace,
.media-workspace,
.task-workspace {
  padding: 24px 32px 32px;
}

/* ---------- 预览弹窗 ---------- */
.preview-dialog :deep(.el-overlay-dialog) {
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-dialog :deep(.el-dialog) {
  display: flex !important;
  flex-direction: column !important;
  height: 96vh;
  max-height: 96vh;
  max-width: 1680px;
  margin: 0 auto;
  overflow: hidden;
  position: relative;
}

:global(.el-input__inner::placeholder),
:global(.el-textarea__inner::placeholder) {
  color: #a8b4c4;
  opacity: 1;
}

.preview-dialog :deep(.el-dialog__header) {
  padding: 14px 72px 8px 24px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.preview-dialog :deep(.el-dialog__headerbtn) {
  position: absolute;
  top: 12px;
  right: 16px;
  z-index: 5;
  width: 40px;
  height: 40px;
  font-size: 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.12);
}

.preview-dialog :deep(.el-dialog__headerbtn .el-dialog__close) {
  color: #607086;
  font-size: 22px;
}

.preview-dialog :deep(.el-dialog__headerbtn .el-dialog__close:hover) {
  color: #172033;
}

.dialog-title {
  font-size: 18px;
  font-weight: 650;
  color: #172033;
}

.preview-dialog :deep(.el-dialog__body) {
  padding: 8px 24px 104px;
  overflow-y: auto;
  flex: 1 1 auto;
  min-height: 0;
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

.preview-dialog :deep(.el-dialog__footer) {
  position: absolute;
  right: 24px;
  bottom: 20px;
  left: 24px;
  z-index: 4;
  padding: 0;
  pointer-events: none;
}

.preview-dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  pointer-events: none;
}

.preview-dialog-footer .el-button,
.preview-dialog-footer .dialog-notice {
  pointer-events: auto;
}

.dialog-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #4f6279;
  font-size: 13px;
  word-break: break-all;
  min-width: 0;
  max-width: min(720px, calc(100% - 220px));
  padding: 8px 12px;
  border: 1px solid #e8ecf2;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.1);
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

  .sidebar.is-collapsed {
    padding: 16px;
  }

  .brand {
    padding-bottom: 14px;
  }

  .sidebar.is-collapsed .brand {
    display: flex;
    justify-content: flex-start;
  }

  .sidebar-collapse-button {
    display: none;
  }

  .nav-menu.el-menu--collapse {
    width: auto;
  }

  .sidebar.is-collapsed .nav-menu :deep(.el-menu-item) {
    justify-content: flex-start;
    padding: 0 20px !important;
  }

  .sidebar.is-collapsed .nav-menu :deep(.el-menu-item .el-icon) {
    margin-right: 5px;
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

  .content-workflow {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .preview-dialog-footer {
    justify-content: flex-end;
  }

  .dialog-notice {
    display: none;
  }
}

@media (max-width: 560px) {
  .content-workflow {
    grid-template-columns: 1fr;
  }
}
</style>
