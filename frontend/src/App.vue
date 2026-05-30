<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { Monitor, Operation, User, VideoPlay } from "@element-plus/icons-vue";

import {
  createPreview,
  createPublishTask,
  type AssetPayload,
  type PlatformKey,
  type PreviewResponse,
  type PublishTaskResponse
} from "@/api/client";
import AccountView from "@/views/AccountView.vue";
import EditorView, { type EditorAssets, type LocalAsset } from "@/views/EditorView.vue";
import PreviewView, { type PlatformDraft } from "@/views/PreviewView.vue";
import PublishFormView, { type PublishForms } from "@/views/PublishFormView.vue";
import TaskView, { type TaskStep } from "@/views/TaskView.vue";

type WorkspaceTab = "preview" | "task" | "account";

const platformLabels: Record<PlatformKey, string> = {
  wechat: "公众号",
  bilibili: "B站",
  zhihu: "知乎",
  xiaohongshu: "小红书"
};

const activeTab = ref<WorkspaceTab>("preview");
const title = ref("AI Agent 发布助手第二阶段说明");
const content = ref(
  [
    "输入一篇内容后，系统会生成公众号、B站、知乎和小红书的模拟草稿。",
    "",
    "第二阶段前端开始准备素材与真实发布参数，真实发布提交仍会在后续确认流程中二次确认。"
  ].join("\n")
);
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

const taskSteps = computed<TaskStep[]>(() => [
  { name: "内容标准化", state: preview.value ? "finish" : "process" },
  { name: "平台渲染", state: preview.value ? "finish" : "wait" },
  { name: "格式校验", state: preview.value ? "finish" : "wait" },
  {
    name: "模拟发布",
    state: taskLoading.value ? "process" : task.value?.status === "succeeded" ? "finish" : task.value?.status === "failed" ? "error" : "wait"
  }
]);

watch(title, (nextTitle) => {
  if (!publishForms.value.bilibili.title || publishForms.value.bilibili.title === "AI Agent 发布助手第二阶段说明") {
    publishForms.value.bilibili.title = nextTitle;
  }
  if (!publishForms.value.wechat.title || publishForms.value.wechat.title === "AI Agent 发布助手第二阶段说明") {
    publishForms.value.wechat.title = nextTitle;
  }
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

async function simulatePublish() {
  if (!preview.value) {
    ElMessage.warning("请先生成预览。");
    return;
  }

  taskLoading.value = true;
  errorMessage.value = "";

  try {
    task.value = await createPublishTask(preview.value.preview_id, selectedPlatforms.value);
    activeTab.value = "task";
    ElMessage.success("模拟发布任务已创建。");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "创建模拟任务失败。";
    ElMessage.error("创建模拟任务失败。");
  } finally {
    taskLoading.value = false;
  }
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
        <el-menu-item index="task">
          <el-icon><Operation /></el-icon>
          <span>模拟任务</span>
        </el-menu-item>
        <el-menu-item index="account">
          <el-icon><User /></el-icon>
          <span>账号管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div>
          <p>第二阶段工作台</p>
          <h1>准备素材、平台草稿和真实发布参数</h1>
        </div>
        <el-tag effect="dark" type="success">Backend Connected</el-tag>
      </el-header>

      <el-main v-if="activeTab === 'account'" class="account-workspace">
        <AccountView />
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
            />
            <PublishFormView
              v-model:forms="publishForms"
              :selected-platforms="selectedPlatforms"
              :validation-report="validationReport"
              :assets="editorAssets"
            />
          </template>
          <TaskView v-else :steps="taskSteps" :task="task" :loading="taskLoading" :error-message="errorMessage" />
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
  min-height: 100vh;
}

.sidebar {
  background: #172033;
  color: #f7fafc;
  padding: 24px 14px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 8px 26px;
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

.account-workspace {
  padding: 24px 32px 32px;
}

.result-panel {
  min-width: 0;
}

@media (max-width: 960px) {
  .app-shell {
    display: block;
  }

  .sidebar {
    width: auto !important;
    padding: 16px;
  }

  .brand {
    padding-bottom: 14px;
  }

  .topbar {
    align-items: flex-start;
    gap: 16px;
    padding: 20px;
  }

  .workspace,
  .account-workspace {
    grid-template-columns: 1fr;
    padding: 20px;
  }
}
</style>
