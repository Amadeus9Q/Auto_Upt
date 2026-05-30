<script setup lang="ts">
import { Camera, Clock } from "@element-plus/icons-vue";

import type { PublishTaskResponse } from "@/api/client";

export interface TaskStep {
  name: string;
  state: "wait" | "process" | "finish" | "error" | "success";
}

defineProps<{
  steps: TaskStep[];
  task: PublishTaskResponse | null;
  loading: boolean;
  errorMessage: string;
}>();
</script>

<template>
  <section class="task-view" v-loading="loading">
    <div class="section-title">
      <div>
        <p>任务状态</p>
        <h2>模拟发布流程</h2>
      </div>
      <el-icon :size="24"><Clock /></el-icon>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <el-steps direction="vertical" :active="2" finish-status="success" class="task-steps">
      <el-step v-for="step in steps" :key="step.name" :title="step.name" :status="step.state" />
    </el-steps>

    <el-empty v-if="!task && !loading && !errorMessage" description="还没有模拟发布任务" />

    <template v-if="task">
      <div class="task-meta">
        <el-tag :type="task.status === 'succeeded' ? 'success' : task.status === 'failed' ? 'danger' : 'info'">
          {{ task.status }}
        </el-tag>
        <span>Task ID：{{ task.task_id }}</span>
      </div>

      <div class="snapshot-list">
        <article v-for="(result, platform) in task.results" :key="platform">
          <div>
            <strong>{{ result?.display_name ?? platform }}</strong>
            <span>{{ result?.message }}</span>
            <small v-if="result?.screenshot_path">{{ result.screenshot_path }}</small>
          </div>
          <el-icon><Camera /></el-icon>
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

.section-title {
  display: flex;
  align-items: center;
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

.task-steps {
  height: 260px;
}

.task-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  color: #607086;
  font-size: 13px;
  word-break: break-all;
}

.snapshot-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.snapshot-list article {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 86px;
  padding: 14px;
  background: #f6f8fb;
  border: 1px dashed #bcc8d7;
  border-radius: 8px;
}

.snapshot-list strong,
.snapshot-list span,
.snapshot-list small {
  display: block;
}

.snapshot-list span {
  margin-top: 4px;
  color: #607086;
  font-size: 13px;
}

.snapshot-list small {
  margin-top: 6px;
  color: #7a8799;
  word-break: break-all;
}

@media (max-width: 680px) {
  .snapshot-list {
    grid-template-columns: 1fr;
  }
}
</style>
