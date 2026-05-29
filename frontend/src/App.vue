<script setup lang="ts">
import { computed, ref } from "vue";
import { Document, Monitor, Operation, VideoPlay } from "@element-plus/icons-vue";

import EditorView from "@/views/EditorView.vue";
import PreviewView from "@/views/PreviewView.vue";
import TaskView from "@/views/TaskView.vue";

type PlatformKey = "wechat" | "bilibili" | "zhihu" | "xiaohongshu";
type WorkspaceTab = "preview" | "task";

interface PlatformDraft {
  key: PlatformKey;
  label: string;
  title: string;
  summary: string;
  status: "ready" | "warning" | "pending";
  metrics: Array<{
    label: string;
    value: string;
  }>;
}

interface TaskStep {
  name: string;
  state: "wait" | "process" | "finish" | "error" | "success";
}

const activeTab = ref<WorkspaceTab>("preview");
const title = ref("AI Agent 发布助手第一阶段说明");
const content = ref(
  [
    "输入一篇内容后，系统会生成公众号、B站、知乎和小红书的模拟草稿。",
    "",
    "第一阶段只处理预览、格式校验、任务状态和截图占位，不接入真实发布。"
  ].join("\n")
);

const wordCount = computed(() => content.value.replace(/\s/g, "").length);

const drafts = computed<PlatformDraft[]>(() => {
  const shortTitle = title.value.trim() || "未命名内容";
  const summary =
    content.value
      .split(/\n+/)
      .map((line) => line.trim())
      .filter(Boolean)
      .slice(0, 2)
      .join(" ") || "等待输入正文后生成平台预览。";

  return [
    {
      key: "wechat",
      label: "公众号",
      title: `${shortTitle} | 长文版`,
      summary,
      status: wordCount.value > 120 ? "ready" : "warning",
      metrics: [
        { label: "标题", value: `${shortTitle.length}/64` },
        { label: "正文", value: `${wordCount.value} 字` }
      ]
    },
    {
      key: "bilibili",
      label: "B站",
      title: `${shortTitle}：视频简介草稿`,
      summary: `${summary} 模拟生成动态文案、简介和标签占位。`,
      status: "pending",
      metrics: [
        { label: "简介", value: `${summary.length}/250` },
        { label: "素材", value: "待补充" }
      ]
    },
    {
      key: "zhihu",
      label: "知乎",
      title: `${shortTitle} 的回答结构`,
      summary: `${summary} 适合扩展为问题背景、核心观点和结论。`,
      status: "ready",
      metrics: [
        { label: "观点", value: "3 段" },
        { label: "引用", value: "模拟校验" }
      ]
    },
    {
      key: "xiaohongshu",
      label: "小红书",
      title: `${shortTitle}｜图文笔记`,
      summary: `${summary} 预留封面、标签和分段标题。`,
      status: wordCount.value > 80 ? "ready" : "warning",
      metrics: [
        { label: "笔记", value: `${wordCount.value}/1000` },
        { label: "标签", value: "5 个" }
      ]
    }
  ];
});

const taskSteps = computed<TaskStep[]>(() => [
  { name: "内容标准化", state: content.value.trim() ? "finish" : "process" },
  { name: "平台渲染", state: wordCount.value > 20 ? "finish" : "wait" },
  { name: "格式校验", state: wordCount.value > 80 ? "finish" : "process" },
  { name: "模拟发布", state: activeTab.value === "task" ? "process" : "wait" }
]);

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
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div>
          <p>第一阶段工作台</p>
          <h1>生成平台草稿、校验报告和模拟任务状态</h1>
        </div>
        <el-tag effect="dark" type="success">Simulation Only</el-tag>
      </el-header>

      <el-main class="workspace">
        <EditorView v-model:title="title" v-model:content="content" :word-count="wordCount" />

        <section class="result-panel">
          <PreviewView v-if="activeTab === 'preview'" :drafts="drafts" />
          <TaskView v-else :steps="taskSteps" :drafts="drafts" />
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

  .workspace {
    grid-template-columns: 1fr;
    padding: 20px;
  }
}
</style>
