<script setup lang="ts">
import { computed } from "vue";
import { InfoFilled, WarningFilled } from "@element-plus/icons-vue";

import type { PlatformKey, ValidationIssue } from "@/api/client";
import type { EditorAssets } from "@/types/media";

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
  contentSourceUrl: string;
  needOpenComment: boolean;
  onlyFansCanComment: boolean;
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

const defaultTab = computed(() => props.selectedPlatforms.find((platform) => ["wechat", "bilibili", "zhihu", "xiaohongshu"].includes(platform)) ?? "wechat");
const coverImage = computed(
  () => props.assets.coverImage ?? props.assets.images.find((image) => image.id === props.assets.coverImageId) ?? props.assets.images[0] ?? null
);
const bilibiliVideo = computed(() => props.assets.videos[0] ?? null);
const wechatIssues = computed(() => props.validationReport.wechat ?? []);

const wechatMissing = computed(() => [
  ...(!forms.value.wechat.title.trim() ? ["标题"] : []),
  ...(!forms.value.wechat.summary.trim() ? ["摘要"] : []),
  ...(!forms.value.wechat.author.trim() ? ["作者"] : []),
  ...(!coverImage.value ? ["封面图片"] : [])
]);

function issueType(issue: ValidationIssue) {
  return issue.level === "error" ? "danger" : issue.level === "warning" ? "warning" : "info";
}
</script>

<template>
  <section class="publish-form-view">

    <el-empty v-if="!selectedPlatforms.length" description="选择平台后查看需要确认的发布内容" />

    <el-tabs v-else :model-value="defaultTab" class="publish-tabs">
      <el-tab-pane v-if="selectedPlatforms.includes('wechat')" label="公众号" name="wechat">
        <div class="platform-heading">
          <el-icon><InfoFilled /></el-icon>
          <strong>公众号发布内容</strong>
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
            <el-input v-model="forms.wechat.title" maxlength="64" show-word-limit placeholder="发布到公众号时显示的文章标题" />
          </el-form-item>
          <el-form-item label="摘要">
            <el-input
              v-model="forms.wechat.summary"
              type="textarea"
              :rows="3"
              resize="none"
              maxlength="120"
              show-word-limit
              placeholder="发布到公众号时显示的文章摘要"
            />
          </el-form-item>
          <el-form-item label="作者">
            <el-input v-model="forms.wechat.author" placeholder="文章作者名称，可留空" />
          </el-form-item>
          <el-form-item label="原文链接">
            <el-input v-model="forms.wechat.contentSourceUrl" placeholder="可选，填写原文或参考来源链接" />
          </el-form-item>
          <el-form-item label="评论设置">
            <div class="radio-row">
              <el-radio-group v-model="forms.wechat.needOpenComment" class="inline-radio-group">
                <el-radio-button :value="true">开启评论</el-radio-button>
                <el-radio-button :value="false">关闭评论</el-radio-button>
              </el-radio-group>
              <el-radio-group
                v-model="forms.wechat.onlyFansCanComment"
                :disabled="!forms.wechat.needOpenComment"
                class="inline-radio-group"
              >
                <el-radio-button :value="false">所有人可评论</el-radio-button>
                <el-radio-button :value="true">仅粉丝可评论</el-radio-button>
              </el-radio-group>
            </div>
          </el-form-item>
          <el-form-item label="发布方式">
            <el-radio-group v-model="forms.wechat.directPublish" class="mode-group">
              <el-radio-button :value="false">先保存到草稿箱</el-radio-button>
              <el-radio-button :value="true">直接提交发布</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <div class="asset-status">
            <span>封面：{{ coverImage?.name || "未选择，默认使用图片列表第一张" }}</span>
            <span>正文图片：{{ assets.images.length }} 张</span>
          </div>
        </el-form>
      </el-tab-pane>

      <el-tab-pane v-if="selectedPlatforms.includes('bilibili')" label="B站" name="bilibili">
        <div class="platform-heading">
          <el-icon><InfoFilled /></el-icon>
          <strong>B站投稿内容</strong>
        </div>
        <el-alert
          class="form-alert"
          title="当前只需要确认封面和视频，其他投稿设置会使用系统默认值。"
          type="info"
          show-icon
          :closable="false"
        />
        <div class="asset-status">
          <span>封面：{{ coverImage?.name || "未选择，默认使用图片列表第一张" }}</span>
          <span>视频：{{ bilibiliVideo?.name || "未选择，默认使用视频列表第一条" }}</span>
        </div>
      </el-tab-pane>

      <el-tab-pane v-if="selectedPlatforms.includes('zhihu')" label="知乎" name="zhihu">
        <el-alert title="当前只展示预览内容，暂不需要填写额外发布设置。" type="info" show-icon :closable="false" />
      </el-tab-pane>

      <el-tab-pane v-if="selectedPlatforms.includes('xiaohongshu')" label="小红书" name="xiaohongshu">
        <el-alert title="当前只展示预览内容，暂不需要填写额外发布设置。" type="info" show-icon :closable="false" />
      </el-tab-pane>
    </el-tabs>

    <div class="risk-note">
      <el-icon><WarningFilled /></el-icon>
      <span>这里只展示发布前需要你确认的内容；没有额外设置的平台会使用系统默认值，并在下一步再次确认。</span>
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

.platform-heading,
.asset-status,
.risk-note,
.issue-list,
.radio-row {
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

.issue-list,
.radio-row {
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.radio-row {
  gap: 16px;
}

.inline-radio-group :deep(.el-radio-button__inner) {
  border-radius: 8px;
}

.mode-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.mode-group :deep(.el-radio-button__inner) {
  border-left: 1px solid var(--el-border-color);
  border-radius: 8px;
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
