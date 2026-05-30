<script setup lang="ts">
import { EditPen, MagicStick } from "@element-plus/icons-vue";

defineProps<{
  wordCount: number;
}>();

const title = defineModel<string>("title", { required: true });
const content = defineModel<string>("content", { required: true });
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

      <el-form-item label="正文">
        <el-input v-model="content" type="textarea" :rows="18" resize="none" placeholder="粘贴 Markdown、富文本要点或视频简介。" />
      </el-form-item>
    </el-form>

    <div class="lint-strip">
      <el-icon><MagicStick /></el-icon>
      <span>当前仅生成模拟预览和校验提示，真实发布能力留给后续阶段。</span>
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
