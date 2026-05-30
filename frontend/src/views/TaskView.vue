<script setup lang="ts">
import { computed } from "vue";
import { Check, Clock, Close, DocumentChecked, Loading, Promotion, Refresh } from "@element-plus/icons-vue";

import type { PlatformKey, PublishResult, PublishTaskResponse } from "@/api/client";

interface TaskStep {
  name: string;
  state: "wait" | "process" | "finish" | "error" | "success";
}

const props = defineProps<{
  tasks: PublishTaskResponse[];
  loading: boolean;
  errorMessage: string;
  actionLoading: string | null;
}>();

const emit = defineEmits<{
  refreshTasks: [];
  refreshTask: [taskId: string];
  publishDraft: [publicationId: string];
}>();

const platformLabels: Record<PlatformKey, string> = {
  wechat: "公众号",
  bilibili: "B站",
  zhihu: "知乎",
  xiaohongshu: "小红书"
};

const statusText = {
  pending: "等待中",
  running: "处理中",
  succeeded: "已完成",
  failed: "失败"
} as const;

const modeText = {
  simulate: "模拟",
  draft: "草稿",
  publish: "真实发布"
} as const;

function finalStepTextForMode(mode: PublishTaskResponse["mode"]) {
  if (mode === "draft") return "草稿已创建";
  if (mode === "simulate") return "模拟完成";
  return "已发布";
}

function stepNamesForMode(mode: PublishTaskResponse["mode"]): [string, string, string] {
  if (mode === "draft") {
    return ["准备素材", "创建草稿", "草稿已创建"];
  }
  if (mode === "simulate") {
    return ["生成任务", "模拟校验", "模拟完成"];
  }
  return ["提交发布", "平台处理", "发布完成"];
}

function progressTextForMode(mode: PublishTaskResponse["mode"]) {
  if (mode === "draft") return "创建中";
  if (mode === "simulate") return "模拟中";
  return "处理中";
}

const taskItems = computed(() =>
  props.tasks.map((task) => {
    const finalStepText = finalStepTextForMode(task.mode);
    const platformTasks = task.platforms.map((platform) => {
      const key = platform as PlatformKey;
      const result = task.results[key] as PublishResult | undefined;
      const failed = result?.status === "failed" || task.status === "failed";
      const succeeded = result?.status === "succeeded";
      const [startStep, processStep, finishStep] = stepNamesForMode(task.mode);
      const steps: TaskStep[] = failed
        ? [
            { name: startStep, state: "finish" },
            { name: processStep, state: "error" },
            { name: "失败", state: "error" }
          ]
        : succeeded
          ? [
              { name: startStep, state: "finish" },
              { name: processStep, state: "finish" },
              { name: finishStep, state: "finish" }
            ]
          : [
              { name: startStep, state: props.loading ? "process" : "wait" },
              { name: processStep, state: "wait" },
              { name: finishStep, state: "wait" }
            ];

      return {
        platform: key,
        label: result?.display_name ?? platformLabels[key] ?? platform,
        result,
        failed,
        succeeded,
        progressText: progressTextForMode(task.mode),
        canPublishDraft:
          task.mode === "draft" &&
          key === "wechat" &&
          Boolean(result?.publication_id) &&
          (result?.external_status === "draft_created" || result?.mode === "draft"),
        steps
      };
    });

    return {
      task,
      finalStepText,
      canRefresh: task.mode !== "simulate" && !task.task_id.startsWith("local-failed-"),
      platformTasks
    };
  })
);

function isActionLoading(action: string, id: string) {
  return props.actionLoading === `${action}:${id}`;
}

function stepIcon(step: TaskStep) {
  if (step.state === "error") return Close;
  if (step.state === "process") return Loading;
  if (step.state === "finish" || step.state === "success") return Check;
  return Clock;
}
</script>

<template>
  <section class="task-view" v-loading="loading">
    <div class="section-title">
      <div>
        <p>任务看板</p>
        <h2>从数据库恢复草稿与发布任务</h2>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="emit('refreshTasks')">刷新列表</el-button>
    </div>

    <el-alert v-if="errorMessage" class="task-alert" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-empty v-if="!tasks.length && !loading && !errorMessage" description="还没有发布任务" />

    <div v-if="taskItems.length" class="task-list">
      <article v-for="taskItem in taskItems" :key="taskItem.task.task_id" class="task-card">
        <div class="task-meta">
          <el-tag :type="taskItem.task.status === 'succeeded' ? 'success' : taskItem.task.status === 'failed' ? 'danger' : 'info'">
            {{ statusText[taskItem.task.status] }}
          </el-tag>
          <el-tag type="info">{{ modeText[taskItem.task.mode] }}</el-tag>
          <span>Task ID：{{ taskItem.task.task_id }}</span>
          <span v-if="taskItem.task.created_at">创建时间：{{ taskItem.task.created_at }}</span>
          <el-button
            v-if="taskItem.canRefresh"
            class="task-action"
            size="small"
            :icon="Refresh"
            :loading="isActionLoading('refresh', taskItem.task.task_id)"
            @click="emit('refreshTask', taskItem.task.task_id)"
          >
            刷新状态
          </el-button>
        </div>

        <div class="platform-task-grid">
          <article v-for="item in taskItem.platformTasks" :key="`${taskItem.task.task_id}-${item.platform}`" class="platform-task-card" :class="{ 'is-failed': item.failed }">
            <header>
              <div>
                <strong>{{ item.label }}</strong>
                <small>{{ modeText[taskItem.task.mode] }}任务</small>
              </div>
              <el-tag :type="item.failed ? 'danger' : item.succeeded ? 'success' : 'info'">
                {{ item.failed ? "失败" : item.succeeded ? taskItem.finalStepText : item.progressText }}
              </el-tag>
            </header>

            <div class="workflow-track" aria-label="平台发布流程">
              <div v-for="(step, index) in item.steps" :key="step.name" class="workflow-step" :class="`is-${step.state}`">
                <span class="workflow-dot">
                  <el-icon><component :is="stepIcon(step)" /></el-icon>
                </span>
                <span class="workflow-label">{{ step.name }}</span>
                <span v-if="index < item.steps.length - 1" class="workflow-line" />
              </div>
            </div>

            <div class="platform-result">
              <el-icon><DocumentChecked /></el-icon>
              <div>
                <span>{{ item.result?.message || "任务已提交，等待平台返回状态。" }}</span>
                <small v-if="item.result?.external_status">平台状态：{{ item.result.external_status }}</small>
                <small v-if="item.result?.external_url">{{ item.result.external_url }}</small>
                <small v-if="item.result?.preview_url">{{ item.result.preview_url }}</small>
                <small v-if="item.result?.screenshot_path">{{ item.result.screenshot_path }}</small>
              </div>
              <el-button
                v-if="item.canPublishDraft && item.result?.publication_id"
                class="platform-action"
                size="small"
                type="primary"
                :icon="Promotion"
                :loading="isActionLoading('publish', item.result.publication_id)"
                @click="emit('publishDraft', item.result.publication_id)"
              >
                发布草稿
              </el-button>
            </div>
          </article>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.task-view {
  min-width: 0;
  padding: 22px;
  background: #ffffff;
  border: 1px solid #dfe5ee;
  border-radius: 8px;
}

.section-title,
.task-meta,
.platform-task-card header,
.platform-result,
.workflow-track,
.workflow-step,
.workflow-dot {
  display: flex;
  align-items: center;
}

.section-title {
  justify-content: space-between;
  margin-bottom: 18px;
}

.section-title p,
.section-title h2 {
  margin: 0;
}

.section-title p {
  color: #607086;
  font-size: 13px;
}

.section-title h2 {
  margin-top: 5px;
  font-size: 20px;
}

.task-alert {
  margin-bottom: 14px;
}

.task-meta {
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 14px;
  color: #607086;
  font-size: 13px;
  word-break: break-all;
}

.task-list {
  display: grid;
  gap: 18px;
}

.task-card {
  min-width: 0;
}

.task-action {
  margin-left: auto;
}

.platform-task-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.platform-task-card {
  display: grid;
  grid-template-columns: minmax(140px, 0.7fr) minmax(360px, 1.6fr) minmax(260px, 1fr);
  align-items: center;
  gap: 18px;
  min-width: 0;
  padding: 18px;
  background: linear-gradient(180deg, #fbfdff 0%, #f6f9fc 100%);
  border: 1px solid #dfe8f3;
  border-radius: 8px;
  box-shadow: 0 1px 0 rgba(23, 32, 51, 0.04);
}

.platform-task-card.is-failed {
  background: linear-gradient(180deg, #fffafa 0%, #fff5f5 100%);
  border-color: #ffd1d1;
}

.platform-task-card header {
  justify-content: space-between;
  gap: 12px;
}

.platform-task-card strong,
.platform-task-card small,
.platform-result span,
.platform-result small {
  display: block;
}

.platform-task-card strong {
  color: #172033;
  font-size: 16px;
}

.platform-task-card small,
.platform-result small {
  margin-top: 4px;
  color: #607086;
  font-size: 12px;
}

.workflow-track {
  min-width: 0;
  width: 100%;
}

.workflow-step {
  min-width: 0;
  flex: 1 1 0;
  gap: 8px;
}

.workflow-step:last-child {
  flex: 0 0 auto;
}

.workflow-dot {
  justify-content: center;
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  color: #7a8799;
  background: #eef3f8;
  border: 1px solid #cfd9e6;
  border-radius: 999px;
}

.workflow-step.is-finish .workflow-dot,
.workflow-step.is-success .workflow-dot {
  color: #ffffff;
  background: #28a745;
  border-color: #28a745;
}

.workflow-step.is-process .workflow-dot {
  color: #ffffff;
  background: #1f6feb;
  border-color: #1f6feb;
}

.workflow-step.is-error .workflow-dot {
  color: #ffffff;
  background: #d93025;
  border-color: #d93025;
}

.workflow-label {
  overflow: hidden;
  color: #253247;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workflow-line {
  height: 2px;
  min-width: 28px;
  flex: 1 1 auto;
  margin: 0 8px;
  background: #d7e0ea;
  border-radius: 999px;
}

.workflow-step.is-finish .workflow-line,
.workflow-step.is-success .workflow-line {
  background: #85d09a;
}

.workflow-step.is-error .workflow-line {
  background: #f2aaa5;
}

.platform-result {
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  color: #4f6279;
  background: #ffffff;
  border: 1px dashed #c8d3e0;
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.45;
}

.platform-result > div {
  min-width: 0;
  flex: 1 1 auto;
}

.platform-result small {
  word-break: break-all;
}

.platform-action {
  flex: 0 0 auto;
}

@media (max-width: 980px) {
  .platform-task-card {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .workflow-track {
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .workflow-step {
    min-width: 120px;
  }

  .task-action,
  .platform-action {
    margin-left: 0;
  }
}
</style>
