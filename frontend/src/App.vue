<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Check, FolderOpened, Monitor, Operation, Right, User, VideoPlay, WarningFilled } from "@element-plus/icons-vue";

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

type WorkspaceTab = "preview" | "confirm" | "task" | "media" | "account";
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

const platformLabels: Record<PlatformKey, string> = {
  wechat: "公众号",
  bilibili: "B站",
  zhihu: "知乎",
  xiaohongshu: "小红书"
};

const realPublishPlatforms: PlatformKey[] = ["wechat", "bilibili", "xiaohongshu"];
const platformAgentStyleGoal: Record<PlatformKey, AgentStyleGoal> = {
  wechat: "professional",
  bilibili: "video",
  zhihu: "knowledge",
  xiaohongshu: "social"
};
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
    preview: "内容预览",
    confirm: "发布确认",
    task: "任务看板",
    media: "多媒体库",
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

watch(title, (nextTitle) => {
  publishForms.value.bilibili.title = nextTitle;
  publishForms.value.wechat.title = nextTitle;
});

watch(tags, (nextTags) => {
  publishForms.value.bilibili.tags = nextTags;
});

const MEDIA_LIBRARY_DB = "auto-upt-media-library";
const MEDIA_LIBRARY_STORE = "assets";
const MEDIA_FOLDERS_KEY = "auto-upt-media-folders";
const MEDIA_COVER_KEY = "auto-upt-cover-image-id";
let mediaPersistTimer: number | null = null;
let mediaHydrated = false;

type StoredAssetRecord = Omit<LocalAsset, "previewUrl" | "file"> & { file: File };

function openMediaLibraryDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(MEDIA_LIBRARY_DB, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(MEDIA_LIBRARY_STORE)) {
        db.createObjectStore(MEDIA_LIBRARY_STORE, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function readStoredAssets(): Promise<StoredAssetRecord[]> {
  const db = await openMediaLibraryDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(MEDIA_LIBRARY_STORE, "readonly");
    const request = tx.objectStore(MEDIA_LIBRARY_STORE).getAll();
    request.onsuccess = () => resolve(request.result as StoredAssetRecord[]);
    request.onerror = () => reject(request.error);
    tx.oncomplete = () => db.close();
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

async function writeStoredAssets(records: StoredAssetRecord[]) {
  const db = await openMediaLibraryDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(MEDIA_LIBRARY_STORE, "readwrite");
    const store = tx.objectStore(MEDIA_LIBRARY_STORE);
    store.clear();
    for (const record of records) {
      store.put(record);
    }
    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

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
  const storedFolders = localStorage.getItem(MEDIA_FOLDERS_KEY);
  if (storedFolders) {
    try {
      mediaFolders.value = JSON.parse(storedFolders) as MediaFolder[];
    } catch {
      mediaFolders.value = [];
    }
  }

  try {
    const records = await readStoredAssets();
    const storedCoverImageId = localStorage.getItem(MEDIA_COVER_KEY);
    const nextAssets: EditorAssets = { images: [], videos: [], audios: [], coverImage: null, coverImageId: storedCoverImageId };
    for (const record of records) {
      const asset: LocalAsset = {
        ...record,
        previewUrl: URL.createObjectURL(record.file),
        file: record.file
      };
      const tab: MediaTab = asset.kind === "image" ? "images" : asset.kind === "video" ? "videos" : "audios";
      nextAssets[tab].push(asset);
    }
    nextAssets.coverImage = nextAssets.images.find((image) => image.id === storedCoverImageId) ?? null;
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
    localStorage.setItem(MEDIA_FOLDERS_KEY, JSON.stringify(mediaFolders.value));
    if (editorAssets.value.coverImageId) {
      localStorage.setItem(MEDIA_COVER_KEY, editorAssets.value.coverImageId);
    } else {
      localStorage.removeItem(MEDIA_COVER_KEY);
    }
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

function collectAssetPayloads(): AssetPayload[] {
  // Collect asset IDs referenced in the body via markers like 【图片：name】 or {{asset:image:id}}
  const referencedIds = new Set<string>();
  const markerPattern = /\{\{asset:(?:image|video|audio):([^}]+)\}\}|【(?:图片|视频|音频)：([^】]+)】/g;
  let match: RegExpExecArray | null;
  while ((match = markerPattern.exec(content.value)) !== null) {
    const displayToken = match[2]?.split("｜id:") ?? [];
    const idOrName = match[1] || displayToken[1] || displayToken[0];
    // Try to match by ID first, then by name
    const byId = allAssets.value.find((a) => a.id === idOrName);
    if (byId) { referencedIds.add(byId.id); continue; }
    const byName = allAssets.value.find((a) => a.name === idOrName || assetFolderPath(a) === idOrName);
    if (byName) referencedIds.add(byName.id);
  }

  const coverImageId = editorAssets.value.coverImageId ?? editorAssets.value.images[0]?.id;
  // Always include cover image
  if (editorAssets.value.coverImage) referencedIds.add(editorAssets.value.coverImage.id);

  return [
    ...(editorAssets.value.coverImage ? [assetToPayload(editorAssets.value.coverImage, "cover", "default_cover")] : []),
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

function collectContentBlocks(): ContentBlockPayload[] {
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

  while ((match = markerPattern.exec(content.value)) !== null) {
    const text = content.value.slice(cursor, match.index).trim();
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
  options: AgentOptimizeOptions,
  platform?: PlatformKey
) {
  const currentDraft = platform ? preview.value?.drafts[platform] : null;
  return {
    title: !options.updateTitle && currentDraft ? currentDraft.title : basePayload.title,
    tags: !options.updateTags && currentDraft ? currentDraft.tags : basePayload.tags,
    update_title: options.updateTitle,
    update_tags: options.updateTags,
    writing_style: options.writingStyle,
    custom_writing_style: options.writingStyle === "custom" ? options.customWritingStyle ?? null : null
  };
}

function preserveAgentDraftMetadata(
  generatedDrafts: PreviewResponse["drafts"],
  options: AgentOptimizeOptions,
  platforms: PlatformKey[]
): PreviewResponse["drafts"] {
  const currentDrafts = preview.value?.drafts ?? {};
  const nextDrafts: PreviewResponse["drafts"] = { ...generatedDrafts };

  for (const platform of platforms) {
    const generatedDraft = nextDrafts[platform];
    const currentDraft = currentDrafts[platform];
    if (!generatedDraft || !currentDraft) {
      continue;
    }

    nextDrafts[platform] = {
      ...generatedDraft,
      title: options.updateTitle ? generatedDraft.title : currentDraft.title,
      tags: options.updateTags ? generatedDraft.tags : currentDraft.tags
    };
  }

  return nextDrafts;
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
      const message = error instanceof Error ? error.message : "同步平台内容失败，请检查网络连接。";
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
    account_ids: {},
    asset_ids: {},
    platform_options: {},
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

function buildPlatformOptions(platforms: PlatformKey[]): NonNullable<PublishTaskCreatePayload["platform_options"]> {
  const platformOptions: NonNullable<PublishTaskCreatePayload["platform_options"]> = {};

  if (platforms.includes("wechat")) {
    const wechatDraft = preview.value?.drafts.wechat;
    platformOptions.wechat = {
      title: publishForms.value.wechat.title.trim() || wechatDraft?.title || title.value.trim(),
      author: publishForms.value.wechat.author.trim(),
      digest: publishForms.value.wechat.summary.trim() || wechatDraft?.summary || "",
      content_source_url: publishForms.value.wechat.contentSourceUrl.trim(),
      need_open_comment: publishForms.value.wechat.needOpenComment,
      only_fans_can_comment: publishForms.value.wechat.needOpenComment && publishForms.value.wechat.onlyFansCanComment,
      direct_publish: publishForms.value.wechat.directPublish
    };
  }

  if (platforms.includes("bilibili")) {
    const bilibiliDraft = preview.value?.drafts.bilibili;
    platformOptions.bilibili = {
      title: publishForms.value.bilibili.title.trim() || bilibiliDraft?.title || title.value.trim(),
      description: publishForms.value.bilibili.description.trim() || bilibiliDraft?.body || content.value,
      tags: parseTagText(publishForms.value.bilibili.tags).length
        ? parseTagText(publishForms.value.bilibili.tags)
        : bilibiliDraft?.tags ?? [],
      tid: 201,
      copyright: 1,
      source: "",
      no_reprint: true,
      dynamic: ""
    };
  }

  if (platforms.includes("xiaohongshu")) {
    const xhsDraft = preview.value?.drafts.xiaohongshu;
    platformOptions.xiaohongshu = {
      title: publishForms.value.xiaohongshu.title.trim() || xhsDraft?.title || title.value.trim(),
      content: publishForms.value.xiaohongshu.content.trim() || xhsDraft?.body || "",
    };
  }

  return platformOptions;
}

async function buildPublishTaskPayload(payload: { platforms: PlatformKey[]; mode: PublishMode }): Promise<PublishTaskCreatePayload> {
  if (!preview.value) {
    throw new Error("请先生成内容预览。");
  }

  const selectedPlatformOptions = buildPlatformOptions(payload.platforms);

  if (payload.mode === "simulate") {
    return {
      preview_id: preview.value.preview_id,
      mode: payload.mode,
      platforms: payload.platforms,
      platform_options: selectedPlatformOptions,
      inline_drafts: preview.value.drafts,
      inline_content_ir: preview.value.content_ir
    };
  }

  const platforms = payload.platforms.filter((platform) => realPublishPlatforms.includes(platform));
  if (!platforms.length) {
    throw new Error("当前版本只有公众号、B站和小红书支持保存草稿或真实发布。");
  }
  if (platforms.length !== payload.platforms.length) {
    throw new Error("知乎当前只能查看模拟结果，暂不能直接发布。");
  }

  const accountIds = await resolveConnectedAccountIds(platforms);
  const assetIds: NonNullable<PublishTaskCreatePayload["asset_ids"]> = {};
  const platformOptions = buildPlatformOptions(platforms);

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
    platformOptions.wechat = {
      ...(platformOptions.wechat ?? {}),
      cover_asset_id: coverAssetId,
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

    const coverAssetId = await ensureBackendAsset(cover, "xiaohongshu_cover");
    const xhsAssetIds = new Set<string>([coverAssetId]);
    for (const image of editorAssets.value.images) {
      xhsAssetIds.add(await ensureBackendAsset(image, image.id === cover.id ? "xiaohongshu_cover" : "xiaohongshu_body_image"));
    }

    // 视频笔记：需要视频素材
    const video = editorAssets.value.videos[0] ?? null;
    if (video) {
      xhsAssetIds.add(await ensureBackendAsset(video, "xiaohongshu_video"));
    }

    assetIds.xiaohongshu = [...xhsAssetIds];
    platformOptions.xiaohongshu = {
      ...(platformOptions.xiaohongshu ?? {}),
      cover_asset_id: coverAssetId,
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
    ElMessage.success("内容已加入发布队列。");
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

  // 获取已有的平台草稿和校验报告
  const previousDrafts = preview.value?.drafts ?? {} as Partial<Record<PlatformKey, DraftPayload>>;
  const previousValidation = preview.value?.validation_report ?? {} as Partial<Record<PlatformKey, ValidationIssue[]>>;

  // 筛选需要生成新草稿的平台：已勾选 且 平台预览区无文本
  const platformsNeedingDrafts = selectedPlatforms.value.filter(
    p => !(previousDrafts[p]?.body?.trim())
  );

  // 如果所有已勾选平台都已有预览文本，无需调用后端
  if (platformsNeedingDrafts.length === 0) {
    if (preview.value) {
      ElMessage.info("所有已勾选平台均已有预览内容，无需重新生成。");
    }
    return;
  }

  previewLoading.value = true;
  errorMessage.value = "";
  task.value = null;

  try {
    // 仅请求需要生成草稿的平台，避免覆盖已有内容
    const payload = buildContentPayload();
    payload.platforms = platformsNeedingDrafts;
    const response = await createPreview(payload);

    // 合并草稿：保留已有文本的平台草稿（含未勾选平台），叠加新生成的草稿
    const mergedDrafts: Partial<Record<PlatformKey, DraftPayload>> = { ...previousDrafts, ...response.drafts };

    // 合并校验报告：已有 + 新生成（新覆盖旧）
    const mergedValidation: Partial<Record<PlatformKey, ValidationIssue[]>> = { ...previousValidation, ...response.validation_report };

    preview.value = {
      ...response,
      drafts: mergedDrafts,
      validation_report: mergedValidation,
    };

    ElMessage.success("预览已生成。");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "预览生成失败，请稍后重试。";
    ElMessage.error("预览生成失败，请稍后重试。");
  } finally {
    previewLoading.value = false;
  }
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
    const basePayload = buildContentPayload();
    const run = await runAgentAdaptPreview({
      ...basePayload,
      ...buildAgentMetadataPayload(basePayload, options),
      preview_id: preview.value?.preview_id ?? null,
      platforms: targetPlatforms,
      style_goal: editorAssets.value.videos.length ? "video" : "professional",
      rewrite_strength: "medium",
      use_llm: "auto",
      persist_preview: !preview.value
    });
    const optimizedDrafts = preserveAgentDraftMetadata(run.drafts, options, targetPlatforms);

    if (!preview.value) {
      preview.value = previewFromAgentRun({
        ...run,
        drafts: optimizedDrafts
      });
    } else {
      preview.value = {
        ...preview.value,
        drafts: {
          ...preview.value.drafts,
          ...optimizedDrafts
        },
        validation_report: {
          ...preview.value.validation_report,
          ...run.validation_report
        }
      };
    }
    ElMessage.success("所选平台的智能优化结果已生成。");
  } catch (error) {
    const message = error instanceof Error ? error.message : "智能优化失败。";
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
    ElMessage.warning("请先生成预览，再优化当前平台内容。");
    return;
  }

  const options = normalizeAgentOptimizeOptions(rawOptions);
  agentLoading.value = true;
  errorMessage.value = "";

  try {
    const basePayload = buildContentPayload();
    const run = await runAgentAdaptPreview({
      ...basePayload,
      ...buildAgentMetadataPayload(basePayload, options, platform),
      preview_id: preview.value.preview_id,
      body: basePayload.body,
      platforms: [platform],
      style_goal: platformAgentStyleGoal[platform],
      rewrite_strength: "medium",
      use_llm: "auto",
      persist_preview: false
    });
    const generatedDraft = run.drafts[platform];
    if (!generatedDraft) {
      throw new Error(`${platformLabels[platform]}没有生成可用的优化内容。`);
    }
    const optimizedDraft = preserveAgentDraftMetadata(
      { [platform]: generatedDraft },
      options,
      [platform]
    )[platform];
    if (!optimizedDraft) {
      throw new Error(`${platformLabels[platform]}没有生成可用的优化内容。`);
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
    const message = error instanceof Error ? error.message : "智能优化失败。";
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

onMounted(async () => {
  await hydrateMediaLibrary();
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
          <el-menu-item index="media">
            <el-icon><FolderOpened /></el-icon>
            <span>多媒体库</span>
          </el-menu-item>
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

      <el-main v-else-if="activeTab === 'media'" class="media-workspace">
        <MediaLibraryView
          v-model:assets="editorAssets"
          v-model:folders="mediaFolders"
        />
      </el-main>

      <el-main v-else-if="activeTab === 'confirm'" class="confirm-workspace">
        <PublishConfirmView
          v-model:publish-forms="publishForms"
          :selected-platforms="selectedPlatforms"
          :loading="taskLoading"
          :validation-report="validationReport"
          :assets="editorAssets"
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
          v-model:media-folders="mediaFolders"
          :word-count="wordCount"
          :preview-loading="previewLoading"
          :agent-loading="agentLoading"
          :publish-loading="taskLoading"
          :has-preview="Boolean(preview)"
          :platform-drafts="preview?.drafts ?? {}"
          :validation-report="validationReport"
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
    justify-content: flex-end;
  }

  .dialog-notice {
    display: none;
  }
}
</style>
