<script setup lang="ts">
import { computed } from "vue";
import { DocumentChecked, InfoFilled, WarningFilled } from "@element-plus/icons-vue";

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
        <p>平台参数</p>
        <h2>按公开 API 准备发布字段</h2>
      </div>
      <el-icon :size="24"><DocumentChecked /></el-icon>
    </div>

    <el-empty
      v-if="!selectedPlatforms.length"
      description="选择平台后查看发布参数"
    />

    <el-tabs v-else :model-value="defaultTab" class="publish-tabs">
      <el-tab-pane v-if="selectedPlatforms.includes('wechat')" label="公众号" name="wechat">
        <div class="platform-heading">
          <el-icon><InfoFilled /></el-icon>
          <strong>公众号草稿箱 API 参数</strong>
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
            <el-input v-model="forms.wechat.title" maxlength="64" show-word-limit placeholder="对应公众号草稿 title 字段" />
          </el-form-item>
          <el-form-item label="摘要">
            <el-input
              v-model="forms.wechat.summary"
              type="textarea"
              :rows="3"
              resize="none"
              maxlength="120"
              show-word-limit
              placeholder="对应公众号草稿 digest 字段，可作为图文摘要"
            />
          </el-form-item>
          <el-form-item label="作者">
            <el-input v-model="forms.wechat.author" placeholder="对应公众号草稿 author 字段" />
          </el-form-item>
          <el-form-item label="原文链接">
            <el-input v-model="forms.wechat.contentSourceUrl" placeholder="对应 content_source_url 字段，可为空" />
          </el-form-item>
          <el-form-item label="评论设置">
            <div class="switch-row">
              <el-switch v-model="forms.wechat.needOpenComment" active-text="开启评论" inactive-text="关闭评论" />
              <el-switch
                v-model="forms.wechat.onlyFansCanComment"
                :disabled="!forms.wechat.needOpenComment"
                active-text="仅粉丝可评论"
                inactive-text="所有人可评论"
              />
            </div>
          </el-form-item>
          <el-form-item label="发布方式">
            <el-switch v-model="forms.wechat.directPublish" active-text="直接提交发布" inactive-text="仅创建草稿" />
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
          <strong>B站发布参数</strong>
        </div>
        <el-alert
          class="form-alert"
          title="未找到稳定公开的官方投稿 API 文档，当前使用系统缺省参数。"
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
        <el-alert
          title="未找到稳定公开的发布 API 文档，发布参数暂缺省。"
          type="info"
          show-icon
          :closable="false"
        />
      </el-tab-pane>

      <el-tab-pane v-if="selectedPlatforms.includes('xiaohongshu')" label="小红书" name="xiaohongshu">
        <el-alert
          title="未找到稳定公开的发布 API 文档，发布参数暂缺省。"
          type="info"
          show-icon
          :closable="false"
        />
      </el-tab-pane>
    </el-tabs>

    <div class="risk-note">
      <el-icon><WarningFilled /></el-icon>
      <span>这里只展示有公开 API 依据的字段；未确认公开接口的平台使用系统缺省参数，并在发布确认中二次确认。</span>
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

.switch-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
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
