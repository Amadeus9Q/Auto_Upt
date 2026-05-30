<script setup lang="ts">
import { Camera, Clock } from "@element-plus/icons-vue";

interface TaskStep {
  name: string;
  state: "wait" | "process" | "finish" | "error" | "success";
}

interface PlatformDraft {
  key: string;
  label: string;
  status: "ready" | "warning" | "pending";
}

defineProps<{
  steps: TaskStep[];
  drafts: PlatformDraft[];
}>();
</script>

<template>
  <section class="task-view">
    <div class="section-title">
      <div>
        <p>任务状态</p>
        <h2>模拟发布流程</h2>
      </div>
      <el-icon :size="24"><Clock /></el-icon>
    </div>

    <el-steps direction="vertical" :active="2" finish-status="success" class="task-steps">
      <el-step v-for="step in steps" :key="step.name" :title="step.name" :status="step.state" />
    </el-steps>

    <div class="snapshot-list">
      <article v-for="draft in drafts" :key="draft.key">
        <div>
          <strong>{{ draft.label }}</strong>
          <span>截图占位记录</span>
        </div>
        <el-icon><Camera /></el-icon>
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
  min-height: 72px;
  padding: 14px;
  background: #f6f8fb;
  border: 1px dashed #bcc8d7;
  border-radius: 8px;
}

.snapshot-list strong,
.snapshot-list span {
  display: block;
}

.snapshot-list span {
  margin-top: 4px;
  color: #607086;
  font-size: 13px;
}

@media (max-width: 680px) {
  .snapshot-list {
    grid-template-columns: 1fr;
  }
}
</style>
