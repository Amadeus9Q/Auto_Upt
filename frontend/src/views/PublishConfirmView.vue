<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { CircleCheck, InfoFilled, WarningFilled } from "@element-plus/icons-vue";

import type { PlatformKey, PublishMode, ValidationIssue } from "@/api/client";
import type { EditorAssets } from "@/types/media";
import { PLATFORM_LABELS } from "@/utils/platforms";
import { useDebounce } from "@/composables/useDebounce";
import PublishFormView, { type PublishForms } from "@/views/PublishFormView.vue";

const { debounce } = useDebounce(150);

const props = defineProps<{
  selectedPlatforms: PlatformKey[];
  loading: boolean;
  validationReport: Partial<Record<PlatformKey, ValidationIssue[]>>;
  assets: EditorAssets;
  editorTitle: string;
  platformDrafts?: Record<string, { title?: string; body?: string; summary?: string }>;
}>();

const emit = defineEmits<{
  back: [];
  submit: [payload: { platforms: PlatformKey[]; mode: PublishMode; useUnifiedSettings: boolean }];
}>();

const publishForms = defineModel<PublishForms>("publishForms", { required: true });
const useUnifiedSettings = ref(true);

// ---- 全局字段（独立状态，同步至各平台） ----
// 统一配置下默认值来自编辑页标题；独立配置下各平台默认值来自 Agent 输出
const globalTitle = ref(props.editorTitle);
const globalSummary = ref(
  props.platformDrafts?.wechat?.summary
  || props.platformDrafts?.bilibili?.body?.slice(0, 120)
  || ""
);

function syncGlobalToPlatforms() {
  const gt = globalTitle.value;
  const gs = globalSummary.value;
  publishForms.value.wechat.title = gt;
  publishForms.value.bilibili.title = gt;
  publishForms.value.xiaohongshu.title = gt;
  publishForms.value.wechat.summary = gs;
  publishForms.value.bilibili.description = gs;
  publishForms.value.xiaohongshu.content = gs;
}

const debouncedSyncToPlatforms = () => debounce(syncGlobalToPlatforms);
watch(globalTitle, debouncedSyncToPlatforms);
watch(globalSummary, debouncedSyncToPlatforms);

// ---- 切换到独立配置时，各平台字段从 Agent 输出取默认值 ----
function populateFromAgent(platform: PlatformKey) {
  const draft = props.platformDrafts?.[platform];
  if (!draft) return;
  if (platform === "wechat") {
    publishForms.value.wechat.title = draft.title || "";
    publishForms.value.wechat.summary = draft.summary || "";
  } else if (platform === "bilibili") {
    publishForms.value.bilibili.title = draft.title || "";
    publishForms.value.bilibili.description = draft.body || "";
  } else if (platform === "xiaohongshu") {
    publishForms.value.xiaohongshu.title = draft.title || "";
    publishForms.value.xiaohongshu.content = draft.body || "";
  }
}

watch(useUnifiedSettings, (unified) => {
  if (!unified) {
    // 切到独立：各平台从 Agent 草稿初始化
    for (const platform of selectedConfirmPlatforms.value) {
      populateFromAgent(platform);
    }
  }
  // 切回统一：globalTitle/globalSummary 保持原值，重新同步至所有平台
  if (unified) {
    syncGlobalToPlatforms();
  }
}, { immediate: true });

const publishablePlatforms: PlatformKey[] = ["wechat", "bilibili", "xiaohongshu"];
const selectedMode = ref<PublishMode>("simulate");
const selectedConfirmPlatforms = ref<PlatformKey[]>([...props.selectedPlatforms]);

const coverImage = computed(
  () => props.assets.coverImage ?? props.assets.images.find((image) => image.id === props.assets.coverImageId) ?? props.assets.images[0] ?? null
);
const bilibiliVideo = computed(() => props.assets.videos[0] ?? null);
const wechatIssues = computed(() => props.validationReport.wechat ?? []);
const hasPublishablePlatform = computed(() => selectedConfirmPlatforms.value.some((p) => publishablePlatforms.includes(p)));
const commonMissing = computed(() => [
  ...(!globalTitle.value.trim() ? ["标题"] : []),
  ...(!globalSummary.value.trim() ? ["摘要/简介"] : []),
  ...(!coverImage.value ? ["封面图片"] : [])
]);

function issueType(issue: ValidationIssue) {
  return issue.level === "error" ? "danger" : issue.level === "warning" ? "warning" : "info";
}

const platformOptions = computed(() => {
  const allowed = selectedMode.value === "simulate" ? props.selectedPlatforms : props.selectedPlatforms.filter((platform) => publishablePlatforms.includes(platform));
  return allowed.map((platform) => ({ label: PLATFORM_LABELS[platform], value: platform }));
});

const selectedIssues = computed(() =>
  selectedConfirmPlatforms.value.flatMap((platform) =>
    (props.validationReport[platform] ?? []).map((issue) => ({
      ...issue,
      platform
    }))
  )
);

const hasRealPublish = computed(() => selectedMode.value === "draft" || selectedMode.value === "publish");

watch(selectedMode, () => {
  const allowed = platformOptions.value.map((option) => option.value);
  selectedConfirmPlatforms.value = selectedConfirmPlatforms.value.filter((platform) => allowed.includes(platform));
  if (!selectedConfirmPlatforms.value.length) {
    selectedConfirmPlatforms.value = [...allowed];
  }
  // 同步发布模式到公众号发布方式：草稿→草稿箱，发布→直接提交
  publishForms.value.wechat.directPublish = selectedMode.value === "publish";
}, { immediate: true });

function submit() {
  if (!selectedConfirmPlatforms.value.length) {
    return;
  }

  emit("submit", {
    platforms: selectedConfirmPlatforms.value,
    mode: selectedMode.value,
    useUnifiedSettings: useUnifiedSettings.value
  });
}
</script>

<template>
  <section class="publish-confirm-view">

    <!-- 平台选择（放在最前面） -->
    <div class="platform-select-section">
      <label class="platform-select-label">发布平台</label>
      <el-checkbox-group v-model="selectedConfirmPlatforms" class="platforms">
        <el-checkbox-button v-for="option in platformOptions" :key="option.value" :value="option.value">
          {{ option.label }}
        </el-checkbox-button>
      </el-checkbox-group>
    </div>

    <!-- 发布设置 -->
    <section class="unified-publish-section">
      <div class="section-title">
        <div>
          <p>发布设置</p>
          <h2>确认发布前需要填写的内容</h2>
        </div>
        <el-radio-group v-model="useUnifiedSettings" class="settings-mode-toggle">
          <el-radio-button :value="true">统一配置</el-radio-button>
          <el-radio-button :value="false">独立配置</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 统一设置表单 -->
      <div v-if="useUnifiedSettings" class="unified-form">
        <el-empty v-if="!selectedConfirmPlatforms.length" description="请在上方选择要发布的平台" />

        <template v-else>
          <div class="platform-heading">
            <el-icon><InfoFilled /></el-icon>
            <strong>统一发布内容（应用于所有选定平台）</strong>
          </div>

          <el-alert
            v-if="commonMissing.length"
            class="form-alert"
            :title="`缺失项：${commonMissing.join('、')}`"
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
            <!-- 通用字段 -->
            <el-form-item label="全局标题">
              <el-input
                v-model="globalTitle"
                maxlength="64"
                show-word-limit
                placeholder="发布时显示的文章标题"
              />
            </el-form-item>
            <el-form-item label="全局摘要 / 简介">
              <el-input
                v-model="globalSummary"
                type="textarea"
                :rows="3"
                resize="none"
                maxlength="120"
                show-word-limit
                placeholder="发布时显示的文章摘要或视频简介"
              />
            </el-form-item>

            <!-- 发布方式（任一可发布平台选中时显示） -->
            <el-form-item v-if="hasPublishablePlatform" label="发布方式">
              <el-radio-group v-model="selectedMode" class="mode-group">
                <el-radio-button value="simulate">模拟</el-radio-button>
                <el-radio-button value="draft">保存草稿</el-radio-button>
                <el-radio-button value="publish">真实发布</el-radio-button>
              </el-radio-group>
            </el-form-item>

            <!-- 公众号专属 -->
            <el-form-item v-if="selectedConfirmPlatforms.includes('wechat')" label="作者">
              <el-input v-model="publishForms.wechat.author" placeholder="文章作者名称，可留空" />
            </el-form-item>
            <el-form-item v-if="selectedConfirmPlatforms.includes('wechat')" label="原文链接">
              <el-input v-model="publishForms.wechat.contentSourceUrl" placeholder="可选，填写原文或参考来源链接" />
            </el-form-item>
            <el-form-item v-if="selectedConfirmPlatforms.includes('wechat')" label="评论设置">
              <div class="radio-row">
                <el-radio-group v-model="publishForms.wechat.needOpenComment" class="inline-radio-group">
                  <el-radio-button :value="true">开启评论</el-radio-button>
                  <el-radio-button :value="false">关闭评论</el-radio-button>
                </el-radio-group>
                <el-radio-group
                  v-model="publishForms.wechat.onlyFansCanComment"
                  :disabled="!publishForms.wechat.needOpenComment"
                  class="inline-radio-group"
                >
                  <el-radio-button :value="false">所有人可评论</el-radio-button>
                  <el-radio-button :value="true">仅粉丝可评论</el-radio-button>
                </el-radio-group>
              </div>
            </el-form-item>

            <!-- B站专属 -->
            <el-form-item v-if="selectedConfirmPlatforms.includes('bilibili')" label="B站标签（逗号分隔）">
              <el-input v-model="publishForms.bilibili.tags" placeholder="例如：科技,AI,编程" />
            </el-form-item>
            <el-form-item v-if="selectedConfirmPlatforms.includes('bilibili')" label="B站分类">
              <el-input v-model="publishForms.bilibili.category" placeholder="例如：科技" />
            </el-form-item>

            <div class="asset-status">
              <span>封面：{{ coverImage?.name || "未选择，默认使用图片列表第一张" }}</span>
              <span v-if="selectedConfirmPlatforms.includes('bilibili')">视频：{{ bilibiliVideo?.name || "未选择，默认使用视频列表第一条" }}</span>
              <span>正文图片：{{ assets.images.length }} 张</span>
            </div>
          </el-form>
        </template>

        <div class="risk-note">
          <el-icon><WarningFilled /></el-icon>
          <span>这里只展示发布前需要你确认的内容；没有额外设置的平台会使用系统默认值，并在下一步再次确认。</span>
        </div>
      </div>

      <!-- 独立设置（仅显示勾选的平台） -->
      <PublishFormView
        v-else
        v-model:forms="publishForms"
        :selected-platforms="selectedConfirmPlatforms"
        :validation-report="validationReport"
        :assets="assets"
      />
    </section>

    <el-alert
      v-if="hasRealPublish"
      class="confirm-alert"
      title="选择保存草稿或真实发布后，系统会把内容提交到对应平台。请先确认账号、素材、标题和封面无误。"
      type="warning"
      show-icon
      :closable="false"
    />

    <el-alert
      v-if="hasRealPublish && selectedConfirmPlatforms.some((platform) => !publishablePlatforms.includes(platform))"
      class="confirm-alert"
      title="知乎当前只能查看模拟结果，暂不能直接发布。"
      type="info"
      show-icon
      :closable="false"
    />

    <div class="risk-panel">
      <header>
        <el-icon><WarningFilled /></el-icon>
        <strong>需要留意的提示</strong>
      </header>
      <el-empty v-if="!selectedIssues.length" description="当前选择的平台没有发现明显问题" />
      <ul v-else>
        <li v-for="issue in selectedIssues" :key="`${issue.platform}-${issue.code}-${issue.field}`">
          <el-tag :type="issue.level === 'error' ? 'danger' : issue.level === 'warning' ? 'warning' : 'info'" size="small">
            {{ PLATFORM_LABELS[issue.platform] }}
          </el-tag>
          <span>{{ issue.field }}：{{ issue.message }}</span>
        </li>
      </ul>
    </div>

    <footer class="confirm-actions">
      <el-button @click="$emit('back')">返回预览</el-button>
      <div class="footer-spacer"></div>
      <el-button type="primary" :icon="CircleCheck" :loading="loading" :disabled="!selectedConfirmPlatforms.length" @click="submit">
        确认发布
      </el-button>
    </footer>
  </section>
</template>

<style scoped>
.publish-confirm-view {
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

/* 统一发布设置区域 */
.unified-publish-section {
  margin-bottom: 18px;
  padding: 22px;
  background: #ffffff;
  border: 1px solid #dfe5ee;
  border-radius: 8px;
}

.settings-mode-toggle {
  display: flex;
  flex-shrink: 0;
}

.settings-mode-toggle :deep(.el-radio-button__inner) {
  border-radius: 8px;
  padding: 6px 16px;
  font-size: 13px;
}

.settings-mode-toggle :deep(.el-radio-button:first-child .el-radio-button__inner) {
  border-left: 1px solid var(--el-border-color);
}

.footer-spacer {
  flex: 1;
}

.unified-form {
  min-width: 0;
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
}

.mode-group,
.platforms {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.platform-select-section {
  margin-bottom: 18px;
}

.platform-select-label {
  display: block;
  margin-bottom: 8px;
  color: #253247;
  font-size: 14px;
  font-weight: 500;
}

.mode-group :deep(.el-radio-button__inner),
.platforms :deep(.el-checkbox-button__inner) {
  border-left: 1px solid var(--el-border-color);
  border-radius: 8px;
}

.confirm-alert {
  margin-bottom: 12px;
}

.risk-panel {
  margin-top: 16px;
  padding: 14px;
  background: #f7f9fc;
  border: 1px solid #e6edf5;
  border-radius: 8px;
}

.risk-panel header,
.risk-panel li,
.confirm-actions {
  display: flex;
  align-items: center;
}

.risk-panel header {
  gap: 8px;
  margin-bottom: 10px;
}

.risk-panel ul {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.risk-panel li {
  gap: 8px;
  color: #4f6279;
  font-size: 13px;
}

.confirm-actions {
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}
</style>
