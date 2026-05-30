<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Check, Monitor, Operation, User, VideoPlay } from "@element-plus/icons-vue";

import {
  createPreview,
  createPublishTask,
  type AssetPayload,
  type PlatformKey,
  type PreviewResponse,
  type PublishMode,
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

const activeTab = ref<WorkspaceTab>("preview");
const title = ref("AI Agent 发布助手第二阶段说明");
const content = ref(["输入一篇内容后，系统会生成多平台草稿。", "", "从预览结果进入发布确认页后，可以选择平台和发布模式。"].join("\n"));
const tags = ref("AI Agent, 内容运营, 自动化");
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
    author: "",
    directPublish: false
  }
});
const preview = ref<PreviewResponse | null>(null);
const task = ref<PublishTaskResponse | null>(null);
const previewLoading = ref(false);
const taskLoading = ref(false);
const errorMessage = ref("");

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
      metrics: [
        { label: "标题", value: `${draft?.title?.length ?? 0} 字` },
        { label: "正文", value: `${draft?.body?.length ?? 0} 字` },
        { label: "校验", value: `${issues.length} 项` }
      ]
    };
  });
});

const taskSteps = computed<TaskStep[]>(() => {
  if (!task.value && taskLoading.value) {
    return [
      { name: "上传中", state: "process" },
      { name: "审核中", state: "wait" },
      { name: "已发布", state: "wait" }
    ];
  }

  if (!task.value) {
    return [
      { name: "上传中", state: "wait" },
      { name: "审核中", state: "wait" },
      { name: "已发布", state: "wait" }
    ];
  }

  if (task.value.status === "failed") {
    return [
      { name: "上传中", state: "finish" },
      { name: "审核中", state: "error" },
      { name: "失败", state: "error" }
    ];
  }

  return [
    { name: "上传中", state: "finish" },
    { name: task.value.mode === "simulate" ? "模拟审核" : "审核中", state: "finish" },
    { name: task.value.mode === "draft" ? "草稿已创建" : task.value.mode === "publish" ? "已发布" : "模拟完成", state: "finish" }
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
    name: asset.name,
    type,
    size: asset.size,
    mime_type: asset.mimeType,
    usage
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
      platforms: selectedPlatforms.value
    });
    activeTab.value = "preview";
    ElMessage.success("预览已由后端生成并保存。");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "生成预览失败。";
    ElMessage.error("生成预览失败。");
  } finally {
    previewLoading.value = false;
  }
}

function enterPublishConfirm() {
  if (!preview.value) {
    ElMessage.warning("请先生成预览。");
    return;
  }
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
    task.value = await createPublishTask(preview.value.preview_id, payload.platforms, payload.mode);
    ElMessage.success(payload.mode === "simulate" ? "模拟发布任务已创建。" : "发布任务已提交。");
  } catch (error) {
    const message = error instanceof Error ? error.message : "创建发布任务失败。";
    task.value = createFailedLocalTask(preview.value.preview_id, payload.platforms, payload.mode, message);
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
          <p>第二阶段工作台</p>
          <h1>预览、确认并提交发布任务</h1>
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
        <TaskView :task="task" :loading="taskLoading" :error-message="errorMessage" />
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

        <section class="result-panel">
          <template v-if="activeTab === 'preview'">
            <PreviewView
              :drafts="drafts"
              :loading="previewLoading"
              :error-message="errorMessage"
              :preview-id="preview?.preview_id ?? ''"
              :created-at="preview?.created_at ?? ''"
              @confirm-publish="enterPublishConfirm"
            />
            <PublishFormView
              v-model:forms="publishForms"
              :selected-platforms="selectedPlatforms"
              :validation-report="validationReport"
              :assets="editorAssets"
            />
          </template>
        </section>
      </el-main>
    </el-container>
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
  display: grid;
  grid-template-columns: minmax(320px, 0.95fr) minmax(360px, 1.05fr);
  gap: 24px;
  padding: 24px 32px 32px;
}

.account-workspace,
.confirm-workspace,
.task-workspace {
  padding: 24px 32px 32px;
}

.result-panel {
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
    grid-template-columns: 1fr;
    padding: 20px;
  }
}
</style>
