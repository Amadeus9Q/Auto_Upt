<script setup lang="ts">
import { Connection, EditPen, MagicStick, Upload } from "@element-plus/icons-vue";

import type { PlatformKey } from "@/api/client";

defineProps<{
  wordCount: number;
  previewLoading: boolean;
  taskLoading: boolean;
  hasPreview: boolean;
}>();

defineEmits<{
  generatePreview: [];
  simulatePublish: [];
}>();

const platformOptions: Array<{ label: string; value: PlatformKey }> = [
  { label: "公众号", value: "wechat" },
  { label: "B站", value: "bilibili" },
  { label: "知乎", value: "zhihu" },
  { label: "小红书", value: "xiaohongshu" }
];

const title = defineModel<string>("title", { required: true });
const content = defineModel<string>("content", { required: true });
const tags = defineModel<string>("tags", { required: true });
const platforms = defineModel<PlatformKey[]>("platforms", { required: true });
</script>

<template>
  <section class="editor-view">
    <div class="section-title">
      <div>
        <p>内容输入</p>
        <h2>统一内容 IR 草稿</h2>
      </div>
      <el-tag type="info">{{ wordCount }} 字</el-tag>
    </div>

    <el-form label-position="top">
      <el-form-item label="标题">
        <el-input v-model="title" :prefix-icon="EditPen" maxlength="64" show-word-limit />
      </el-form-item>

      <el-form-item label="平台">
        <el-checkbox-group v-model="platforms" class="platforms">
          <el-checkbox-button v-for="option in platformOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </el-checkbox-button>
        </el-checkbox-group>
      </el-form-item>

      <el-form-item label="标签">
        <el-input v-model="tags" placeholder="用逗号或空格分隔" />
      </el-form-item>

      <el-form-item label="正文">
        <el-input v-model="content" type="textarea" :rows="15" resize="none" placeholder="粘贴 Markdown、富文本要点或视频简介。" />
      </el-form-item>
    </el-form>

    <div class="action-row">
      <el-button type="primary" :icon="Connection" :loading="previewLoading" @click="$emit('generatePreview')">
        生成预览
      </el-button>
      <el-button :icon="Upload" :disabled="!hasPreview" :loading="taskLoading" @click="$emit('simulatePublish')">
        模拟发布
      </el-button>
    </div>

    <div class="lint-strip">
      <el-icon><MagicStick /></el-icon>
      <span>当前后端只执行模拟预览和模拟发布，不会调用真实平台账号。</span>
    </div>
  </section>
</template>

<style scoped>
.editor-view {
  min-width: 0;
  padding: 22px;
  background: #ffffff;
  border: 1px solid #dfe5ee;
  border-radius: 8px;
}

.section-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
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

.platforms {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.platforms :deep(.el-checkbox-button__inner) {
  border-radius: 8px;
  border-left: 1px solid var(--el-border-color);
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 14px;
}

.lint-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  color: #4f6279;
  background: #eef3f8;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
}
</style>
