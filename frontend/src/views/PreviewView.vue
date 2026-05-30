<script setup lang="ts">
import { Collection, WarningFilled } from "@element-plus/icons-vue";

interface PlatformDraft {
  key: string;
  label: string;
  title: string;
  summary: string;
  status: "ready" | "warning" | "pending";
  metrics: Array<{
    label: string;
    value: string;
  }>;
}

defineProps<{
  drafts: PlatformDraft[];
}>();

const statusMap = {
  ready: { label: "可预览", type: "success" },
  warning: { label: "需补充", type: "warning" },
  pending: { label: "待素材", type: "info" }
} as const;
</script>

<template>
  <section class="preview-view">
    <div class="section-title">
      <div>
        <p>平台预览</p>
        <h2>四平台模拟草稿</h2>
      </div>
      <el-icon :size="24"><Collection /></el-icon>
    </div>

    <div class="draft-grid">
      <article v-for="draft in drafts" :key="draft.key" class="draft-card">
        <header>
          <strong>{{ draft.label }}</strong>
          <el-tag :type="statusMap[draft.status].type">{{ statusMap[draft.status].label }}</el-tag>
        </header>
        <h3>{{ draft.title }}</h3>
        <p>{{ draft.summary }}</p>
        <div class="metric-row">
          <span v-for="metric in draft.metrics" :key="metric.label">
            {{ metric.label }}：{{ metric.value }}
          </span>
        </div>
      </article>
    </div>

    <div class="notice">
      <el-icon><WarningFilled /></el-icon>
      <span>预览结果来自前端模拟数据，后续可替换为后端 adapter render 和 validate 输出。</span>
    </div>
  </section>
</template>

<style scoped>
.preview-view {
  min-width: 0;
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

.draft-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.draft-card {
  min-width: 0;
  min-height: 190px;
  padding: 18px;
  background: #ffffff;
  border: 1px solid #dfe5ee;
  border-radius: 8px;
}

.draft-card header,
.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.draft-card h3 {
  margin: 18px 0 10px;
  font-size: 17px;
  line-height: 1.4;
}

.draft-card p {
  min-height: 66px;
  margin: 0;
  color: #4f6279;
  line-height: 1.55;
}

.metric-row {
  margin-top: 18px;
  color: #607086;
  font-size: 13px;
  flex-wrap: wrap;
}

.notice {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 18px;
  padding: 12px 14px;
  color: #7a541f;
  background: #fff6e3;
  border-radius: 8px;
  font-size: 14px;
}

@media (max-width: 680px) {
  .draft-grid {
    grid-template-columns: 1fr;
  }
}
</style>
