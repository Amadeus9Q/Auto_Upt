<script setup lang="ts">
import { computed } from "vue";
import { DocumentChecked, InfoFilled, VideoCamera, WarningFilled } from "@element-plus/icons-vue";

import type { PlatformKey, ValidationIssue } from "@/api/client";
import type { EditorAssets } from "@/views/EditorView.vue";

export interface BilibiliPublishForm {
  title: string;
  description: string;
  tags: string;
  category: string;
}

export interface WechatPublishForm {
  title: string;
  summary: string;
  author: string;
  directPublish: boolean;
}

export interface PublishForms {
  bilibili: BilibiliPublishForm;
  wechat: WechatPublishForm;
}

const props = defineProps<{
  selectedPlatforms: PlatformKey[];
  validationReport: Partial<Record<PlatformKey, ValidationIssue[]>>;
  assets: EditorAssets;
}>();

const forms = defineModel<PublishForms>("forms", { required: true });

const defaultTab = computed(() => (props.selectedPlatforms.includes("bilibili") ? "bilibili" : "wechat"));
const coverImage = computed(
  () => props.assets.coverImage ?? props.assets.images.find((image) => image.id === props.assets.coverImageId) ?? props.assets.images[0] ?? null
);
const bilibiliVideo = computed(() => props.assets.videos[0] ?? null);
const bilibiliIssues = computed(() => props.validationReport.bilibili ?? []);
const wechatIssues = computed(() => props.validationReport.wechat ?? []);

const bilibiliMissing = computed(() => [
  ...(!forms.value.bilibili.title.trim() ? ["标题"] : []),
  ...(!forms.value.bilibili.description.trim() ? ["简介"] : []),
  ...(!forms.value.bilibili.tags.trim() ? ["标签"] : []),
  ...(!forms.value.bilibili.category.trim() ? ["分区"] : []),
  ...(!coverImage.value ? ["封面图片"] : []),
  ...(!bilibiliVideo.value ? ["视频文件"] : [])
]);

const wechatMissing = computed(() => [
  ...(!forms.value.wechat.title.trim() ? ["标题"] : []),
  ...(!forms.value.wechat.summary.trim() ? ["摘要"] : []),
  ...(!coverImage.value ? ["封面图片"] : []),
  ...(props.assets.images.length === 0 ? ["正文图片"] : [])
]);

function issueType(issue: ValidationIssue) {
  return issue.level === "error" ? "danger" : issue.level === "warning" ? "warning" : "info";
}
</script>

<template>
  <section class="publish-form-view">
    <div class="section-title">
      <div>
        <p>发布表单</p>
        <h2>发布参数配置</h2>
      </div>
      <el-icon :size="24"><DocumentChecked /></el-icon>
    </div>

    <el-empty
      v-if="!selectedPlatforms.includes('bilibili') && !selectedPlatforms.includes('wechat')"
      description="请选择公众号或 B 站后填写发布参数"
    />

    <el-tabs v-else :model-value="defaultTab" class="publish-tabs">
      <el-tab-pane v-if="selectedPlatforms.includes('bilibili')" label="B站" name="bilibili">
        <div class="platform-heading">
          <el-icon><VideoCamera /></el-icon>
          <strong>B 站稿件信息</strong>
        </div>

        <el-alert
          v-if="bilibiliMissing.length"
          class="form-alert"
          :title="`缺失项：${bilibiliMissing.join('、')}`"
          type="warning"
          show-icon
          :closable="false"
        />

        <div v-if="bilibiliIssues.length" class="issue-list">
          <el-tag v-for="issue in bilibiliIssues" :key="`${issue.code}-${issue.field}`" :type="issueType(issue)">
            {{ issue.field }}：{{ issue.message }}
          </el-tag>
        </div>

        <el-form label-position="top">
          <el-form-item label="标题">
            <el-input v-model="forms.bilibili.title" maxlength="80" show-word-limit />
          </el-form-item>
          <el-form-item label="简介">
            <el-input v-model="forms.bilibili.description" type="textarea" :rows="4" resize="none" />
          </el-form-item>
          <el-form-item label="标签">
            <el-input v-model="forms.bilibili.tags" placeholder="多个关键词，逗号分隔" />
          </el-form-item>
          <el-form-item label="分区">
            <el-select v-model="forms.bilibili.category" placeholder="请选择分区">
              <el-option label="科技 / 计算机技术" value="tech" />
              <el-option label="知识 / 职业职场" value="knowledge" />
              <el-option label="生活 / 日常" value="life" />
            </el-select>
          </el-form-item>
          <div class="asset-status">
            <span>封面：{{ coverImage?.name || "未选择，将默认使用首张图片" }}</span>
            <span>视频：{{ bilibiliVideo?.name || "未选择，将默认使用首个视频" }}</span>
          </div>
        </el-form>
      </el-tab-pane>

      <el-tab-pane v-if="selectedPlatforms.includes('wechat')" label="公众号" name="wechat">
        <div class="platform-heading">
          <el-icon><InfoFilled /></el-icon>
          <strong>公众号图文信息</strong>
        </div>

        <el-alert
          v-if="wechatMissing.length"
          class="form-alert"
          :title="`缺失项：${wechatMissing.join('、')}`"
          type="warning"
          show-icon
          :closable="false"
        />

        <div v-if="wechatIssues.length" class="issue-list">
          <el-tag v-for="issue in wechatIssues" :key="`${issue.code}-${issue.field}`" :type="issueType(issue)">
            {{ issue.field }}：{{ issue.message }}
          </el-tag>
        </div>

        <el-form label-position="top">
          <el-form-item label="标题">
            <el-input v-model="forms.wechat.title" maxlength="64" show-word-limit />
          </el-form-item>
          <el-form-item label="摘要">
            <el-input v-model="forms.wechat.summary" type="textarea" :rows="3" resize="none" maxlength="120" show-word-limit />
          </el-form-item>
          <el-form-item label="作者">
            <el-input v-model="forms.wechat.author" placeholder="留空将使用默认作者名称" />
          </el-form-item>
          <el-form-item label="发布方式">
            <el-switch v-model="forms.wechat.directPublish" active-text="直接提交发布" inactive-text="仅创建草稿" />
          </el-form-item>
          <div class="asset-status">
            <span>封面：{{ coverImage?.name || "未选择，将默认使用首张图片" }}</span>
            <span>正文图片：{{ assets.images.length }} 张</span>
          </div>
        </el-form>
      </el-tab-pane>
    </el-tabs>

    <div class="risk-note">
      <el-icon><WarningFilled /></el-icon>
      <span>此处展示发布参数与平台校验结果，真实发布将在后续流程中二次确认。</span>
    </div>
  </section>
</template>

<style scoped>
.publish-form-view {
  min-width: 0;
  margin-top: 18px;
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

.platform-heading,
.asset-status,
.risk-note,
.issue-list {
  display: flex;
  align-items: center;
}

.platform-heading {
  gap: 8px;
  margin-bottom: 14px;
  color: #253247;
}

.form-alert {
  margin-bottom: 14px;
}

.issue-list {
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.asset-status {
  flex-wrap: wrap;
  gap: 10px;
  color: #607086;
  font-size: 13px;
}

.asset-status span {
  padding: 8px 10px;
  background: #f7f9fc;
  border: 1px solid #e6edf5;
  border-radius: 8px;
}

.risk-note {
  gap: 8px;
  margin-top: 16px;
  padding: 12px 14px;
  color: #4f6279;
  background: #eef3f8;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
}
</style>
