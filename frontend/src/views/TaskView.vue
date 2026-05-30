<script setup lang="ts">
import { computed } from "vue";
import { Check, Clock, Close, DocumentChecked, Loading } from "@element-plus/icons-vue";

import type { PlatformKey, PublishResult, PublishTaskResponse } from "@/api/client";

interface TaskStep {
  name: string;
  state: "wait" | "process" | "finish" | "error" | "success";
}

const props = defineProps<{
  task: PublishTaskResponse | null;
  loading: boolean;
  errorMessage: string;
}>();

const platformLabels: Record<PlatformKey, string> = {
  wechat: "公众号",
  bilibili: "B站",
  zhihu: "知乎",
  xiaohongshu: "小红书"
};

const statusText = {
  pending: "等待中",
  running: "上传中",
  succeeded: "已完成",
  failed: "失败"
} as const;

const modeText = {
  simulate: "模拟",
  draft: "草稿",
  publish: "真实发布"
} as const;

const finalStepText = computed(() => {
  if (!props.task) return "已发布";
  if (props.task.mode === "draft") return "草稿已创建";
  if (props.task.mode === "simulate") return "模拟完成";
  return "已发布";
});

const platformTasks = computed(() => {
  if (!props.task) return [];

  return props.task.platforms.map((platform) => {
    const key = platform as PlatformKey;
    const result = props.task?.results[key] as PublishResult | undefined;
    const failed = result?.status === "failed" || props.task?.status === "failed";
    const succeeded = result?.status === "succeeded";
    const steps: TaskStep[] = failed
      ? [
          { name: "上传中", state: "finish" },
          { name: "审核中", state: "error" },
          { name: "失败", state: "error" }
        ]
      : succeeded
        ? [
            { name: "上传中", state: "finish" },
            { name: "审核中", state: "finish" },
            { name: finalStepText.value, state: "finish" }
          ]
        : [
            { name: "上传中", state: props.loading ? "process" : "wait" },
            { name: "审核中", state: "wait" },
            { name: finalStepText.value, state: "wait" }
          ];

    return {
      platform: key,
      label: result?.display_name ?? platformLabels[key] ?? platform,
      result,
      failed,
      succeeded,
      steps
    };
  });
});

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
        <h2>一行一个平台确认发布状态</h2>
      </div>
      <el-icon :size="24"><Clock /></el-icon>
    </div>

    <el-alert v-if="errorMessage" class="task-alert" :title="errorMessage" type="error" show-icon :closable="false" />
    <el-empty v-if="!task && !loading && !errorMessage" description="还没有发布任务" />

    <template v-if="task">
      <div class="task-meta">
        <el-tag :type="task.status === 'succeeded' ? 'success' : task.status === 'failed' ? 'danger' : 'info'">
          {{ statusText[task.status] }}
        </el-tag>
        <el-tag type="info">{{ modeText[task.mode] }}</el-tag>
        <span>Task ID：{{ task.task_id }}</span>
      </div>

      <div class="platform-task-grid">
        <article v-for="item in platformTasks" :key="item.platform" class="platform-task-card" :class="{ 'is-failed': item.failed }">
          <header>
            <div>
              <strong>{{ item.label }}</strong>
              <small>{{ modeText[task.mode] }}任务</small>
            </div>
            <el-tag :type="item.failed ? 'danger' : item.succeeded ? 'success' : 'info'">
              {{ item.failed ? "失败" : item.succeeded ? finalStepText : "处理中" }}
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
              <small v-if="item.result?.preview_url">{{ item.result.preview_url }}</small>
              <small v-if="item.result?.screenshot_path">{{ item.result.screenshot_path }}</small>
            </div>
          </div>
        </article>
      </div>
    </template>
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

.platform-result small {
  word-break: break-all;
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
}
</style>
