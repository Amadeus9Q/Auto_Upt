<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { CircleCheck, InfoFilled, Setting, Refresh, WarningFilled } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import { getAccounts, type AccountConnection, type AccountStatus, type PlatformKey, type PublishMode, type ValidationIssue } from "@/api/client";
import type { EditorAssets } from "@/types/media";
import { getErrorMessage } from "@/utils/errors";
import { PLATFORM_LABELS } from "@/utils/platforms";
import AccountView from "@/views/AccountView.vue";
import PublishFormView, { type PublishForms } from "@/views/PublishFormView.vue";

const props = defineProps<{
  selectedPlatforms: PlatformKey[];
  loading: boolean;
  validationReport: Partial<Record<PlatformKey, ValidationIssue[]>>;
  assets: EditorAssets;
  platformDrafts?: Record<string, { title?: string; body?: string; summary?: string }>;
}>();

const emit = defineEmits<{
  back: [];
  submit: [payload: { platforms: PlatformKey[]; mode: PublishMode; useUnifiedSettings: boolean; forms: PublishForms }];
}>();

const publishForms = defineModel<PublishForms>("publishForms", { required: true });
const useUnifiedSettings = ref(true);

type ConfirmPlatformDraft = { title?: string; body?: string; summary?: string };

function draftFor(platform: PlatformKey): ConfirmPlatformDraft | undefined {
  return props.platformDrafts?.[platform];
}

function normalizedText(value?: string) {
  return value?.trim() ?? "";
}

function draftTitle(platform: PlatformKey) {
  return normalizedText(draftFor(platform)?.title);
}

function draftSummary(platform: PlatformKey) {
  const draft = draftFor(platform);
  return normalizedText(draft?.summary) || normalizedText(draft?.body?.slice(0, 120));
}

// ---- 全局字段（独立状态，同步至各平台） ----
// 统一配置留空时使用各平台草稿兜底；独立配置默认值来自对应平台草稿。
const globalTitle = ref("");
const globalSummary = ref("");

function cloneForms(forms: PublishForms): PublishForms {
  return {
    wechat: { ...forms.wechat },
    bilibili: { ...forms.bilibili },
    xiaohongshu: { ...forms.xiaohongshu }
  };
}

const independentForms = ref<PublishForms>(cloneForms(publishForms.value));
independentForms.value.wechat.title = props.platformDrafts?.wechat?.title || independentForms.value.wechat.title;
independentForms.value.wechat.summary = props.platformDrafts?.wechat?.summary || independentForms.value.wechat.summary;
independentForms.value.bilibili.title = props.platformDrafts?.bilibili?.title || independentForms.value.bilibili.title;
independentForms.value.bilibili.description = props.platformDrafts?.bilibili?.body || independentForms.value.bilibili.description;
independentForms.value.xiaohongshu.title = props.platformDrafts?.xiaohongshu?.title || independentForms.value.xiaohongshu.title;
independentForms.value.xiaohongshu.content = props.platformDrafts?.xiaohongshu?.body || independentForms.value.xiaohongshu.content;

const publishablePlatforms: PlatformKey[] = ["wechat", "bilibili", "xiaohongshu"];
const selectedMode = ref<PublishMode>("simulate");
const selectedConfirmPlatforms = ref<PlatformKey[]>([...props.selectedPlatforms]);
const accounts = ref<AccountConnection[]>([]);
const accountsLoading = ref(false);
const accountsError = ref("");
const accountConfigVisible = ref(false);
const configuringPlatform = ref<PlatformKey | null>(null);

const coverImage = computed(
  () => props.assets.coverImage ?? props.assets.images.find((image) => image.id === props.assets.coverImageId) ?? props.assets.images[0] ?? null
);
const bilibiliVideo = computed(() => props.assets.videos[0] ?? null);
const wechatIssues = computed(() => props.validationReport.wechat ?? []);
const hasPublishablePlatform = computed(() => selectedConfirmPlatforms.value.some((p) => publishablePlatforms.includes(p)));
const confirmPublishUnavailableReason = computed(() =>
  selectedConfirmPlatforms.value.length ? "" : "请先选择一个已连接的平台"
);
const commonMissing = computed(() => [
  ...(
    !globalTitle.value.trim() && selectedConfirmPlatforms.value.some((platform) => !draftTitle(platform))
      ? ["标题"]
      : []
  ),
  ...(
    !globalSummary.value.trim() && selectedConfirmPlatforms.value.some((platform) => !draftSummary(platform))
      ? ["摘要/简介"]
      : []
  ),
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
const platformAccountOptions = computed(() =>
  platformOptions.value.map((option) => ({
    ...option,
    account: accounts.value.find((account) => account.platform === option.value) ?? null
  }))
);
const connectedPlatformValues = computed(() =>
  platformAccountOptions.value
    .filter((option) => option.account?.status === "connected")
    .map((option) => option.value)
);
const configurablePlatforms: PlatformKey[] = ["wechat", "bilibili"];

function isAccountConnected(account: AccountConnection | null) {
  return account?.status === "connected";
}

function isAccountConfigurable(platform: PlatformKey) {
  return configurablePlatforms.includes(platform);
}

function accountConfigTooltip(platform: PlatformKey) {
  return isAccountConfigurable(platform) ? "配置账号" : "账号配置功能待上线";
}

function handlePlatformCardClick(account: AccountConnection | null) {
  if (!isAccountConnected(account)) {
    ElMessage.warning("该平台尚未连接，请先点击右侧配置按钮完成配置");
  }
}

function openAccountConfig(platform: PlatformKey) {
  if (!isAccountConfigurable(platform)) {
    return;
  }
  configuringPlatform.value = platform;
  accountConfigVisible.value = true;
}

function handleAccountConfigClosed() {
  configuringPlatform.value = null;
  void refreshAccountStatuses();
}

function handleAccountUpdated(account: AccountConnection) {
  const accountIndex = accounts.value.findIndex((item) => item.platform === account.platform);
  if (accountIndex >= 0) {
    accounts.value.splice(accountIndex, 1, account);
  } else {
    accounts.value.push(account);
  }
  accountsError.value = "";
}

function accountStatusMeta(status?: AccountStatus) {
  return status === "connected"
    ? { label: "账号已连接", className: "is-connected" }
    : { label: status === "expired" ? "账号已过期" : status === "error" ? "账号连接异常" : "账号未配置", className: "is-disconnected" };
}

async function refreshAccountStatuses() {
  accountsLoading.value = true;
  accountsError.value = "";
  try {
    accounts.value = await getAccounts();
  } catch (error) {
    accountsError.value = getErrorMessage(error, "账号状态刷新失败，请稍后重试。");
  } finally {
    accountsLoading.value = false;
  }
}

watch(selectedMode, () => {
  const allowed = platformOptions.value.map((option) => option.value);
  selectedConfirmPlatforms.value = selectedConfirmPlatforms.value.filter((platform) => allowed.includes(platform));
}, { immediate: true });

watch(connectedPlatformValues, (connected) => {
  selectedConfirmPlatforms.value = selectedConfirmPlatforms.value.filter((platform) => connected.includes(platform));
}, { immediate: true });

onMounted(() => {
  void refreshAccountStatuses();
});

function effectiveForms(): PublishForms {
  const forms = cloneForms(useUnifiedSettings.value ? publishForms.value : independentForms.value);
  if (useUnifiedSettings.value) {
    forms.wechat.title = globalTitle.value;
    forms.bilibili.title = globalTitle.value;
    forms.xiaohongshu.title = globalTitle.value;
    forms.wechat.summary = globalSummary.value;
    forms.bilibili.description = globalSummary.value;
    forms.xiaohongshu.content = globalSummary.value;
  }
  forms.wechat.directPublish = selectedMode.value === "publish";
  return forms;
}

function submit() {
  if (!selectedConfirmPlatforms.value.length) {
    return;
  }

  emit("submit", {
    platforms: selectedConfirmPlatforms.value,
    mode: selectedMode.value,
    useUnifiedSettings: useUnifiedSettings.value,
    forms: effectiveForms()
  });
}
</script>

<template>
  <section class="publish-confirm-view">

    <section class="account-status-section">
      <header class="account-status-header">
        <div>
          <strong>发布平台与账号联通</strong>
          <small>勾选本次发布平台，并确认对应账号联通状态。</small>
        </div>
        <el-button :icon="Refresh" :loading="accountsLoading" @click="refreshAccountStatuses">
          刷新账号状态
        </el-button>
      </header>

      <el-alert
        v-if="accountsError"
        :title="accountsError"
        type="error"
        show-icon
        :closable="false"
      />

      <el-checkbox-group v-model="selectedConfirmPlatforms" class="account-status-grid">
        <article
          v-for="item in platformAccountOptions"
          :key="item.value"
          class="account-status-card"
          :class="{
            'is-selected': selectedConfirmPlatforms.includes(item.value),
            'is-disconnected': !isAccountConnected(item.account)
          }"
          @click="handlePlatformCardClick(item.account)"
        >
          <el-checkbox
            :value="item.value"
            :disabled="!isAccountConnected(item.account)"
            class="account-platform-checkbox"
          >
            {{ item.label }}
          </el-checkbox>
          <el-tooltip :content="accountStatusMeta(item.account?.status).label" placement="top">
            <span class="account-status-dot" :class="accountStatusMeta(item.account?.status).className" />
          </el-tooltip>
          <el-tooltip :content="accountConfigTooltip(item.value)" placement="top">
            <span class="account-config-action" @click.stop>
              <el-button
                size="small"
                text
                circle
                :icon="Setting"
                :disabled="!isAccountConfigurable(item.value)"
                :aria-label="accountConfigTooltip(item.value)"
                @click="openAccountConfig(item.value)"
              />
            </span>
          </el-tooltip>
        </article>
      </el-checkbox-group>
    </section>

    <el-dialog
      v-model="accountConfigVisible"
      :title="configuringPlatform ? `配置${PLATFORM_LABELS[configuringPlatform]}账号` : '配置平台账号'"
      width="min(92vw, 520px)"
      destroy-on-close
      @closed="handleAccountConfigClosed"
    >
      <AccountView
        :focused-platform="configuringPlatform"
        :initial-accounts="accounts"
        configuration-only
        compact
        @account-updated="handleAccountUpdated"
      />
    </el-dialog>

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
                placeholder="留空则使用各平台草稿标题"
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
                placeholder="留空则使用各平台草稿摘要或正文"
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
              <el-input v-model="publishForms.bilibili.category" placeholder="分区 ID，例如：201" />
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
      <template v-else>
        <el-form label-position="top" class="independent-mode-form">
          <el-form-item v-if="hasPublishablePlatform" label="发布方式">
            <el-radio-group v-model="selectedMode" class="mode-group">
              <el-radio-button value="simulate">模拟</el-radio-button>
              <el-radio-button value="draft">保存草稿</el-radio-button>
              <el-radio-button value="publish">真实发布</el-radio-button>
            </el-radio-group>
          </el-form-item>
        </el-form>
        <PublishFormView
          v-model:forms="independentForms"
          :selected-platforms="selectedConfirmPlatforms"
          :validation-report="validationReport"
          :assets="assets"
        />
      </template>
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
      <el-button @click="$emit('back')">返回编辑所选平台</el-button>
      <div class="footer-spacer"></div>
      <el-tooltip
        :content="confirmPublishUnavailableReason"
        placement="top"
        :disabled="!confirmPublishUnavailableReason"
      >
        <span class="disabled-action-tooltip">
          <el-button
            type="primary"
            :icon="CircleCheck"
            :loading="loading"
            :disabled="Boolean(confirmPublishUnavailableReason)"
            @click="submit"
          >
            确认发布
          </el-button>
        </span>
      </el-tooltip>
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

.disabled-action-tooltip {
  display: inline-flex;
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

.mode-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.account-status-section {
  display: grid;
  gap: 12px;
  margin-bottom: 18px;
  padding: 16px;
  background: #f8fafc;
  border: 1px solid #dfe5ee;
  border-radius: 8px;
}

.account-status-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.account-status-header > div {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.account-status-header small,
.account-status-card small {
  color: #607086;
  font-size: 12px;
}

.account-status-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.account-status-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: #ffffff;
  border: 1px solid #e2eaf3;
  border-radius: 8px;
}

.account-status-card.is-selected {
  border-color: #1f6feb;
  box-shadow: 0 0 0 3px rgba(31, 111, 235, 0.08);
}

.account-status-card.is-disconnected {
  cursor: not-allowed;
}

.account-status-card.is-disconnected .account-platform-checkbox {
  cursor: not-allowed;
}

.account-platform-checkbox {
  min-width: 0;
  flex: 1;
  margin-right: 0;
}

.account-platform-checkbox :deep(.el-checkbox__label) {
  overflow: hidden;
  color: #253247;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-status-card .el-button {
  flex-shrink: 0;
}

.account-config-action {
  display: inline-flex;
  flex-shrink: 0;
}

.account-status-dot {
  flex-shrink: 0;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.account-status-dot.is-connected {
  background: #2f9e64;
  box-shadow: 0 0 0 3px rgba(47, 158, 100, 0.12);
}

.account-status-dot.is-disconnected {
  background: #a8b4c4;
}

@media (max-width: 1280px) {
  .account-status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .account-status-grid {
    grid-template-columns: 1fr;
  }
}

.platform-select-label {
  display: block;
  margin-bottom: 8px;
  color: #253247;
  font-size: 14px;
  font-weight: 500;
}

.mode-group :deep(.el-radio-button__inner),
.inline-radio-group :deep(.el-radio-button__inner) {
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
