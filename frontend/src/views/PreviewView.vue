<script setup lang="ts">
import { Collection, WarningFilled } from "@element-plus/icons-vue";

import type { PlatformKey, ValidationIssue } from "@/api/client";

export interface PlatformDraft {
  key: PlatformKey;
  label: string;
  title: string;
  summary: string;
  body: string;
  tags: string[];
  status: "ready" | "warning" | "pending";
  issues: ValidationIssue[];
  metrics: Array<{
    label: string;
    value: string;
  }>;
}

defineProps<{
  drafts: PlatformDraft[];
  loading: boolean;
  errorMessage: string;
  previewId: string;
  createdAt: string;
}>();

const statusMap = {
  ready: { label: "可预览", type: "success" },
  warning: { label: "需检查", type: "warning" },
  pending: { label: "待生成", type: "info" }
} as const;
</script>

<template>
  <section class="preview-view" v-loading="loading">
    <div class="section-title">
      <div>
        <p>平台预览</p>
        <h2>后端生成草稿</h2>
      </div>
      <el-icon :size="24"><Collection /></el-icon>
    </div>

    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon :closable="false" />

    <el-empty v-if="!loading && drafts.length === 0 && !errorMessage" description="还没有生成预览" />

    <div v-else class="draft-grid">
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
        <el-collapse v-if="draft.body || draft.issues.length" class="draft-detail">
          <el-collapse-item title="草稿详情" name="body">
            <pre>{{ draft.body }}</pre>
            <div v-if="draft.tags.length" class="tag-row">
              <el-tag v-for="tag in draft.tags" :key="tag" size="small">{{ tag }}</el-tag>
            </div>
          </el-collapse-item>
          <el-collapse-item v-if="draft.issues.length" title="校验报告" name="issues">
            <ul>
              <li v-for="issue in draft.issues" :key="`${issue.code}-${issue.field}`">
                {{ issue.level }} / {{ issue.field }}：{{ issue.message }}
              </li>
            </ul>
          </el-collapse-item>
        </el-collapse>
      </article>
    </div>

    <div v-if="previewId" class="notice">
      <el-icon><WarningFilled /></el-icon>
      <span>Preview ID：{{ previewId }}<template v-if="createdAt">，创建时间：{{ createdAt }}</template></span>
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

.draft-detail {
  margin-top: 12px;
}

pre {
  max-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  color: #253247;
  font-family: inherit;
  line-height: 1.55;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}

.notice {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 18px;
  padding: 12px 14px;
  color: #4f6279;
  background: #eef3f8;
  border-radius: 8px;
  font-size: 14px;
  word-break: break-all;
}

@media (max-width: 680px) {
  .draft-grid {
    grid-template-columns: 1fr;
  }
}
</style>
