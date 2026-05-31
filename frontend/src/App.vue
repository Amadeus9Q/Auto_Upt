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
  uploadAsset,
  type AssetPayload,
  type ContentBlockPayload,
  type PlatformKey,
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
  }
});
const preview = ref<PreviewResponse | null>(null);
const task = ref<PublishTaskResponse | null>(null);
const tasks = ref<PublishTaskResponse[]>([]);
const previewLoading = ref(false);
const taskLoading = ref(false);
const taskHistoryLoading = ref(false);
const taskActionLoading = ref<string | null>(null);
const errorMessage = ref("");
const previewDialogVisible = ref(false);
const publishFormExpanded = ref<string[]>([]);

const wordCount = computed(() => content.value.replace(/\s/g, "").length);

const tagList = computed(() =>
  tags.value
    .split(/[,，\s]+/)
    .map((tag) => tag.trim())
    .filter(Boolean)
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
      label: platformLabels[platform],
      title: draft?.title ?? platformLabels[platform],
      summary: draft?.summary || draft?.body || "后端未返回摘要。",
      body: draft?.body ?? "",
      tags: draft?.tags ?? [],
      status: warnings > 0 ? "warning" : "ready",
      issues,
      rich_body: draft?.rich_body ?? [],
      cover_image: draft?.cover_image ?? null,
      body_blocks: draft?.body_blocks ?? [],
      media_slots: draft?.media_slots ?? {},
      author: draft?.author,
      metadata: draft?.metadata,
      content_points: draft?.content_points ?? [],
      highlights: draft?.highlights ?? [],
      zhihu_blocks: draft?.zhihu_blocks ?? [],
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
      throw new Error(`请先在账号管理中连接${platformLabels[platform]}账号，再执行草稿或真实发布。`);
    }
    accountIds[platform] = account.account_id;
  }

  return accountIds;
}

function buildPlatformOptions(platforms: PlatformKey[]): NonNullable<PublishTaskCreatePayload["platform_options"]> {
  const platformOptions: NonNullable<PublishTaskCreatePayload["platform_options"]> = {};

  if (platforms.includes("wechat")) {
    platformOptions.wechat = {
      title: publishForms.value.wechat.title.trim() || title.value.trim(),
      author: publishForms.value.wechat.author.trim(),
      digest: publishForms.value.wechat.summary.trim(),
      content_source_url: publishForms.value.wechat.contentSourceUrl.trim(),
      need_open_comment: publishForms.value.wechat.needOpenComment,
      only_fans_can_comment: publishForms.value.wechat.needOpenComment && publishForms.value.wechat.onlyFansCanComment,
      direct_publish: publishForms.value.wechat.directPublish
    };
  }

  if (platforms.includes("bilibili")) {
    platformOptions.bilibili = {
      title: publishForms.value.bilibili.title.trim() || title.value.trim(),
      description: publishForms.value.bilibili.description.trim() || content.value,
      tags: parseTagText(publishForms.value.bilibili.tags),
      tid: 201,
      copyright: 1,
      source: "",
      no_reprint: true,
      dynamic: ""
    };
  }

  return platformOptions;
}

async function buildPublishTaskPayload(payload: { platforms: PlatformKey[]; mode: PublishMode }): Promise<PublishTaskCreatePayload> {
  if (!preview.value) {
    throw new Error("请先生成预览。");
  }

  const selectedPlatformOptions = buildPlatformOptions(payload.platforms);

  if (payload.mode === "simulate") {
    return {
      preview_id: preview.value.preview_id,
      mode: payload.mode,
      platforms: payload.platforms,
      platform_options: selectedPlatformOptions
    };
  }

  const platforms = payload.platforms.filter((platform) => realPublishPlatforms.includes(platform));
  if (!platforms.length) {
    throw new Error("本阶段草稿和真实发布仅支持公众号与 B站。");
  }
  if (platforms.length !== payload.platforms.length) {
    throw new Error("知乎和小红书本阶段不支持草稿或真实发布，请改用模拟发布。");
  }

  const accountIds = await resolveConnectedAccountIds(platforms);
  const assetIds: NonNullable<PublishTaskCreatePayload["asset_ids"]> = {};
  const platformOptions = buildPlatformOptions(platforms);

  if (platforms.includes("wechat")) {
    const cover = getCoverImage();
    if (!cover) {
      throw new Error("公众号草稿或真实发布需要先上传封面图。");
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
      throw new Error("B站草稿或真实发布需要先上传视频文件。");
    }

    const cover = getCoverImage();
    const videoAssetId = await ensureBackendAsset(video, "bilibili_video");
    const coverAssetId = cover ? await ensureBackendAsset(cover, "bilibili_cover") : undefined;
    assetIds.bilibili = coverAssetId ? [videoAssetId, coverAssetId] : [videoAssetId];

    platformOptions.bilibili = {
      ...(platformOptions.bilibili ?? {}),
      video_asset_id: videoAssetId,
      cover_asset_id: coverAssetId
    };
  }

  return {
    preview_id: preview.value.preview_id,
    mode: payload.mode,
    platforms,
    account_ids: accountIds,
    asset_ids: assetIds,
    platform_options: platformOptions
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
      ElMessage.success("发布任务列表已刷新。");
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "加载发布任务失败。";
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
    ElMessage.success("任务状态已刷新。");
  } catch (error) {
    const message = error instanceof Error ? error.message : "刷新任务状态失败。";
    errorMessage.value = message;
    ElMessage.error(message);
  } finally {
    taskActionLoading.value = null;
  }
}

async function publishDraftFromTask(publicationId: string) {
  try {
    await ElMessageBox.confirm("确认将该平台草稿提交发布？提交后会调用真实平台发布接口。", "发布草稿确认", {
      confirmButtonText: "确认发布",
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
    ElMessage.success("草稿已提交发布。");
  } catch (error) {
    const message = error instanceof Error ? error.message : "草稿提交发布失败。";
    errorMessage.value = message;
    ElMessage.error(message);
  } finally {
    taskActionLoading.value = null;
  }
}

async function generatePreview() {
  if (!content.value.trim()) {
    ElMessage.warning("请先输入正文内容。");
    return;
  }

  previewLoading.value = true;
  errorMessage.value = "";
  task.value = null;

  try {
    preview.value = await createPreview({
      title: title.value.trim() || undefined,
      body: content.value,
      content_type: editorAssets.value.videos.length ? "video" : collectAssetPayloads().length ? "mixed" : "article",
      tags: tagList.value,
      assets: collectAssetPayloads(),
      content_blocks: collectContentBlocks(),
      cover_asset_id: editorAssets.value.coverImage?.id ?? editorAssets.value.coverImageId ?? null,
      platforms: selectedPlatforms.value
    });
    previewDialogVisible.value = true;
    ElMessage.success("预览已由后端生成并保存。");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "生成预览失败。";
    ElMessage.error("生成预览失败。");
  } finally {
    previewLoading.value = false;
  }
}

function handleDraftUpdate(updatedDrafts: PlatformDraft[]) {
  if (!preview.value) return;
  // 将编辑后的标题/正文/标签同步回 preview.drafts，保障发布流使用最新数据
  for (const ud of updatedDrafts) {
    const existing = preview.value.drafts[ud.key];
    if (!existing) continue;
    existing.title = ud.title;
    existing.body = ud.body;
    existing.tags = ud.tags;
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

async function simulatePublish() {
  await submitPublish({ platforms: selectedPlatforms.value, mode: "simulate" });
}

function selectTab(key: string) {
  activeTab.value = key as WorkspaceTab;
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
          <span>多平台内容投放助手</span>
        </div>
      </div>

      <el-menu :default-active="activeTab" class="nav-menu" @select="selectTab">
        <el-menu-item index="preview">
          <el-icon><Monitor /></el-icon>
          <span>平台预览</span>
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
          <p>内容投放工作台</p>
          <h1>编辑内容、生成预览并确认发布</h1>
        </div>
        <el-tag effect="dark" type="success">Backend Connected</el-tag>
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
          :task-loading="taskLoading"
          :has-preview="Boolean(preview)"
          @generate-preview="generatePreview"
          @simulate-publish="simulatePublish"
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
        <span class="dialog-title">多平台投放预览</span>
      </template>

      <div class="preview-dialog-body">
        <PreviewView
          :drafts="drafts"
          :loading="previewLoading"
          :error-message="errorMessage"
          :preview-id="preview?.preview_id ?? ''"
          :created-at="preview?.created_at ?? ''"
          @confirm-publish="enterPublishConfirm"
          @update:drafts="handleDraftUpdate"
        />

        <el-collapse v-model="publishFormExpanded" class="publish-form-collapse">
          <el-collapse-item name="publish-params">
            <template #title>
              <span class="collapse-title-row">
                <el-icon class="collapse-arrow">
                  <ArrowDown v-if="publishFormExpanded.includes('publish-params')" />
                  <ArrowRight v-else />
                </el-icon>
                <span>平台 API 参数</span>
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
      </div>

      <template #footer>
        <div class="preview-dialog-footer">
          <div class="dialog-notice">
            <el-icon><WarningFilled /></el-icon>
            <span>Preview ID：{{ preview?.preview_id }}<template v-if="preview?.created_at">，创建时间：{{ preview.created_at }}</template></span>
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
.task-workspace {
  padding: 24px 32px 32px;
}

/* ---------- 预览弹窗 ---------- */
/* 让弹窗撑满视口，内部区域正确滚动 */
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

/* 确保关闭按钮 × 始终可见 */
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
