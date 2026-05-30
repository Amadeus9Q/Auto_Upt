<script setup lang="ts">
import { computed, ref } from "vue";

import type { PlatformKey, ValidationIssue } from "@/api/client";
import WechatPreview from "@/views/WechatPreview.vue";
import type { RichBlock } from "@/views/WechatPreview.vue";

export interface PlatformDraft {
  key: PlatformKey;
  label: string;
  title: string;
  summary: string;
  body: string;
  tags: string[];
  status: "ready" | "warning" | "pending";
  issues: ValidationIssue[];
  metrics: Array<{ label: string; value: string }>;
  rich_body?: RichBlock[];
  cover_image?: { url?: string; name?: string } | null;
  author?: string;
  metadata?: { estimated_read_time_minutes?: number; source_word_count?: number };
}

const props = defineProps<{
  drafts: PlatformDraft[];
  loading: boolean;
  errorMessage: string;
  previewId: string;
  createdAt: string;
}>();

defineEmits<{
  confirmPublish: [];
}>();

const currentPlatform = ref<PlatformKey>("wechat");

const activeDraft = computed(() => props.drafts.find((d) => d.key === currentPlatform.value) ?? null);

function selectPlatform(key: string) {
  currentPlatform.value = key as PlatformKey;
}

function issueType(issue: ValidationIssue) {
  if (issue.level === "error") return "danger";
  if (issue.level === "warning") return "warning";
  return "info";
}
</script>

<template>
  <section class="preview-view" v-loading="loading">
    <!-- 头部：平台切换 -->
    <header class="preview-header">
      <div class="platform-switcher">
        <el-radio-group
          v-model="currentPlatform"
          size="default"
          @change="selectPlatform"
        >
          <el-radio-button
            v-for="draft in drafts"
            :key="draft.key"
            :value="draft.key"
          >
            {{ draft.label }}
            <el-tag
              v-if="draft.status === 'warning'"
              size="small"
              type="warning"
              effect="plain"
              class="switcher-badge"
            >
              {{ draft.issues.length }}
            </el-tag>
          </el-radio-button>
        </el-radio-group>
      </div>
    </header>

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      :closable="false"
      class="preview-alert"
    />

    <el-empty
      v-if="!loading && drafts.length === 0 && !errorMessage"
      description="还没有生成预览"
    />

    <!-- 公众号：手机框预览 -->
    <template v-if="activeDraft">
      <WechatPreview
        v-if="activeDraft.key === 'wechat'"
        :title="activeDraft.title"
        :summary="activeDraft.summary"
        :body="activeDraft.body"
        :tags="activeDraft.tags"
        :rich-body="activeDraft.rich_body"
        :cover-image="activeDraft.cover_image"
        :author="activeDraft.author"
        :metadata="activeDraft.metadata"
      />

      <!-- 其他平台：表单式 -->
      <el-form v-else label-position="top" class="preview-form">
        <el-form-item label="标题">
          <el-input
            :model-value="activeDraft.title"
            readonly
            class="readonly-field"
          >
            <template #suffix>
              <span class="char-count">{{ activeDraft.title.length }} 字</span>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="摘要">
          <el-input
            :model-value="activeDraft.summary"
            type="textarea"
            :rows="3"
            readonly
            resize="none"
            class="readonly-field"
          />
        </el-form-item>

        <el-form-item label="正文">
          <div class="body-preview">
            <pre>{{ activeDraft.body }}</pre>
          </div>
        </el-form-item>

        <el-form-item v-if="activeDraft.tags.length" label="标签">
          <div class="tag-row">
            <el-tag
              v-for="tag in activeDraft.tags"
              :key="tag"
              effect="plain"
              round
            >
              {{ tag }}
            </el-tag>
          </div>
        </el-form-item>

        <!-- 指标行 -->
        <div class="metric-row">
          <span v-for="metric in activeDraft.metrics" :key="metric.label">
            {{ metric.label }}：<strong>{{ metric.value }}</strong>
          </span>
        </div>

        <!-- 校验报告 -->
        <el-collapse v-if="activeDraft.issues.length" class="issues-collapse">
          <el-collapse-item :title="`校验报告（${activeDraft.issues.length} 项）`" name="issues">
            <div class="issue-list">
              <div
                v-for="issue in activeDraft.issues"
                :key="`${issue.code}-${issue.field}`"
                class="issue-item"
              >
                <el-tag :type="issueType(issue)" size="small" effect="plain">
                  {{ issue.level }}
                </el-tag>
                <span class="issue-field">{{ issue.field }}</span>
                <span class="issue-msg">{{ issue.message }}</span>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-form>
    </template>
  </section>
</template>

<style scoped>
.preview-view {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

/* ---------- 头部 ---------- */
.preview-header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 16px;
}

.platform-switcher {
  flex-shrink: 0;
}

.platform-switcher :deep(.el-radio-button__inner) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.switcher-badge {
  margin-left: 2px;
  font-size: 11px;
  padding: 0 4px;
  height: 18px;
  line-height: 18px;
}

.preview-alert {
  margin-bottom: 18px;
}

/* ---------- 表单 ---------- */
.preview-form {
  flex: 1;
}

.readonly-field :deep(.el-input__inner),
.readonly-field :deep(.el-textarea__inner) {
  background: #f7f9fb;
  color: #253247;
  cursor: default;
}

.char-count {
  color: #9aa9bb;
  font-size: 12px;
  user-select: none;
}

.body-preview {
  max-height: 260px;
  overflow: auto;
  border: 1px solid #dfe5ee;
  border-radius: 6px;
  background: #f7f9fb;
}

.body-preview pre {
  margin: 0;
  padding: 14px 16px;
  white-space: pre-wrap;
  word-break: break-word;
  color: #253247;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.65;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.metric-row {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  margin-bottom: 18px;
  padding: 10px 14px;
  background: #f0f3f7;
  border-radius: 6px;
  color: #607086;
  font-size: 13px;
}

.metric-row strong {
  color: #172033;
}

/* ---------- 校验 ---------- */
.issues-collapse {
  margin-top: 4px;
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.issue-item {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-size: 13px;
}

.issue-field {
  color: #607086;
  min-width: 60px;
}

.issue-msg {
  color: #253247;
}

@media (max-width: 680px) {
  .preview-header {
    justify-content: flex-start;
  }
}
</style>
