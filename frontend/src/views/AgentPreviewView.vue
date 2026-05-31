<script setup lang="ts">
import { computed, ref } from "vue";
import { Check, DocumentChecked, MagicStick, Tickets } from "@element-plus/icons-vue";

import type { AgentAdaptPreviewResponse, PlatformKey } from "@/api/client";

const props = defineProps<{
  run: AgentAdaptPreviewResponse | null;
}>();

const emit = defineEmits<{
  applyMetadata: [];
  applyBody: [];
  usePreview: [];
  close: [];
}>();

const platformLabels: Record<PlatformKey, string> = {
  wechat: "公众号",
  bilibili: "B站",
  zhihu: "知乎",
  xiaohongshu: "小红书"
};

const activePanel = ref(["metadata", "rewrite", "drafts"]);

const draftItems = computed(() => {
  if (!props.run) return [];
  return Object.entries(props.run.drafts).map(([platform, draft]) => ({
    platform: platform as PlatformKey,
    label: platformLabels[platform as PlatformKey],
    title: draft?.title ?? "",
    summary: draft?.body || draft?.summary || "",
    tags: draft?.tags ?? [],
    issues: props.run?.validation_report[platform as PlatformKey] ?? []
  }));
});

const keywordText = computed(() => props.run?.metadata.tags.join(", ") ?? "");

const llmStatusLabel = computed(() => {
  switch (props.run?.llm_status) {
    case "available":
      return "LLM 已启用";
    case "degraded":
      return "LLM 降级（使用规则引擎）";
    default:
      return "LLM 未启用";
  }
});

const llmStatusType = computed(() => {
  switch (props.run?.llm_status) {
    case "available":
      return "success";
    case "degraded":
      return "warning";
    default:
      return "info";
  }
});
</script>

<template>
  <section v-if="run" class="agent-preview-view">
    <header class="agent-header">
      <div>
        <p>智能优化结果</p>
        <h2>先预览，再应用到编辑器</h2>
      </div>
      <div class="header-tags">
        <el-tag type="success">{{ run.status }}</el-tag>
        <el-tag :type="llmStatusType">{{ llmStatusLabel }}</el-tag>
      </div>
    </header>

    <el-collapse v-model="activePanel">
      <el-collapse-item name="metadata">
        <template #title>
          <span class="panel-title">
            <el-icon><Tickets /></el-icon>
            标题与关键词
          </span>
        </template>
        <div class="metadata-grid">
          <div>
            <small>建议标题</small>
            <strong>{{ run.metadata.title }}</strong>
          </div>
          <div>
            <small>摘要</small>
            <span>{{ run.metadata.summary }}</span>
          </div>
          <div>
            <small>关键词</small>
            <el-input :model-value="keywordText" readonly placeholder="多个关键词，逗号分隔" />
          </div>
        </div>
        <el-button type="primary" :icon="Check" @click="emit('applyMetadata')">应用标题/关键词</el-button>
      </el-collapse-item>

      <el-collapse-item name="rewrite">
        <template #title>
          <span class="panel-title">
            <el-icon><MagicStick /></el-icon>
            优化后的正文
          </span>
        </template>
        <el-input :model-value="run.rewritten_content.body" type="textarea" :rows="10" resize="none" readonly />
        <div class="inline-actions">
          <el-tag type="info">写作方向：{{ run.rewritten_content.style_goal }}</el-tag>
          <el-tag type="info">调整幅度：{{ run.rewritten_content.rewrite_strength }}</el-tag>
          <el-tag type="info">生成方式：{{ run.rewritten_content.source }}</el-tag>
          <el-button type="primary" :icon="Check" @click="emit('applyBody')">使用这版正文</el-button>
        </div>
      </el-collapse-item>

      <el-collapse-item name="drafts">
        <template #title>
          <span class="panel-title">
            <el-icon><DocumentChecked /></el-icon>
            各平台预览内容
          </span>
        </template>
        <div class="draft-grid">
          <article v-for="draft in draftItems" :key="draft.platform" class="draft-item">
            <header>
              <strong>{{ draft.label }}</strong>
              <el-tag :type="draft.issues.some((issue) => issue.level === 'error') ? 'danger' : draft.issues.length ? 'warning' : 'success'">
                {{ draft.issues.length }} 项提示
              </el-tag>
            </header>
            <h3>{{ draft.title }}</h3>
            <p>{{ draft.summary }}</p>
            <div class="tag-row">
              <el-tag v-for="tag in draft.tags" :key="`${draft.platform}-${tag}`" size="small" effect="plain">{{ tag }}</el-tag>
            </div>
          </article>
        </div>
      </el-collapse-item>

    </el-collapse>

    <footer class="agent-actions">
      <span v-if="run.preview_id">预览记录：{{ run.preview_id }}</span>
      <el-button @click="emit('close')">放弃</el-button>
      <el-button type="success" :disabled="!run.preview_id" @click="emit('usePreview')">使用该预览发布</el-button>
    </footer>
  </section>
</template>

<style scoped>
.agent-preview-view {
  min-width: 0;
}

.agent-header,
.panel-title,
.inline-actions,
.draft-item header,
.tag-row,
.agent-actions {
  display: flex;
  align-items: center;
}

.agent-header {
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.agent-header p,
.agent-header h2 {
  margin: 0;
}

.agent-header p,
.metadata-grid small,
.draft-item p,
.agent-actions span {
  color: #607086;
  font-size: 13px;
}

.agent-header h2 {
  margin-top: 4px;
  font-size: 20px;
}

.header-tags {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.panel-title {
  gap: 8px;
}

.metadata-grid {
  display: grid;
  gap: 12px;
  margin-bottom: 14px;
}

.metadata-grid small,
.metadata-grid strong,
.metadata-grid span {
  display: block;
}

.metadata-grid strong {
  margin-top: 4px;
  color: #172033;
  font-size: 18px;
}

.metadata-grid .el-tag {
  margin: 6px 6px 0 0;
}

.inline-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

.draft-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.draft-item {
  min-width: 0;
  padding: 14px;
  background: #f8fafc;
  border: 1px solid #e2eaf3;
  border-radius: 8px;
}

.draft-item header {
  justify-content: space-between;
  gap: 10px;
}

.draft-item h3 {
  margin: 10px 0 6px;
  color: #172033;
  font-size: 15px;
}

.draft-item p {
  display: -webkit-box;
  overflow: hidden;
  min-height: 38px;
  margin: 0 0 10px;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-height: 1.45;
}

.tag-row {
  flex-wrap: wrap;
  gap: 6px;
}

.agent-actions {
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid #e8ecf2;
}

.agent-actions span {
  margin-right: auto;
  word-break: break-all;
}
</style>
