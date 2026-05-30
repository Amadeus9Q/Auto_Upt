<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { CircleCheck, Promotion, WarningFilled } from "@element-plus/icons-vue";

import type { PlatformKey, PublishMode, ValidationIssue } from "@/api/client";

const props = defineProps<{
  selectedPlatforms: PlatformKey[];
  loading: boolean;
  validationReport: Partial<Record<PlatformKey, ValidationIssue[]>>;
}>();

const emit = defineEmits<{
  back: [];
  submit: [payload: { platforms: PlatformKey[]; mode: PublishMode }];
}>();

const platformLabels: Record<PlatformKey, string> = {
  wechat: "公众号",
  bilibili: "B站",
  zhihu: "知乎",
  xiaohongshu: "小红书"
};

const publishablePlatforms: PlatformKey[] = ["wechat", "bilibili"];
const selectedMode = ref<PublishMode>("simulate");
const selectedConfirmPlatforms = ref<PlatformKey[]>([...props.selectedPlatforms]);

const platformOptions = computed(() => {
  const allowed = selectedMode.value === "simulate" ? props.selectedPlatforms : props.selectedPlatforms.filter((platform) => publishablePlatforms.includes(platform));
  return allowed.map((platform) => ({ label: platformLabels[platform], value: platform }));
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
});

function submit() {
  if (!selectedConfirmPlatforms.value.length) {
    return;
  }

  emit("submit", {
    platforms: selectedConfirmPlatforms.value,
    mode: selectedMode.value
  });
}
</script>

<template>
  <section class="publish-confirm-view">
    <div class="section-title">
      <div>
        <p>发布确认</p>
        <h2>选择平台与发布模式</h2>
      </div>
      <el-icon :size="24"><Promotion /></el-icon>
    </div>

    <el-form label-position="top">
      <el-form-item label="发布模式">
        <el-radio-group v-model="selectedMode" class="mode-group">
          <el-radio-button value="simulate">模拟</el-radio-button>
          <el-radio-button value="draft">草稿</el-radio-button>
          <el-radio-button value="publish">真实发布</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="发布平台">
        <el-checkbox-group v-model="selectedConfirmPlatforms" class="platforms">
          <el-checkbox-button v-for="option in platformOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </el-checkbox-button>
        </el-checkbox-group>
      </el-form-item>
    </el-form>

    <el-alert
      v-if="hasRealPublish"
      class="confirm-alert"
      title="真实发布或创建草稿将调用平台官方接口，请在提交前仔细确认账号、素材、标题、封面及平台合规性。"
      type="warning"
      show-icon
      :closable="false"
    />

    <el-alert
      v-if="hasRealPublish && selectedPlatforms.some((platform) => !publishablePlatforms.includes(platform))"
      class="confirm-alert"
      title="知乎和小红书当前阶段暂不支持真实发布，仅可选择模拟模式。"
      type="info"
      show-icon
      :closable="false"
    />

    <div class="risk-panel">
      <header>
        <el-icon><WarningFilled /></el-icon>
        <strong>校验风险</strong>
      </header>
      <el-empty v-if="!selectedIssues.length" description="当前选择的平台未发现校验问题" />
      <ul v-else>
        <li v-for="issue in selectedIssues" :key="`${issue.platform}-${issue.code}-${issue.field}`">
          <el-tag :type="issue.level === 'error' ? 'danger' : issue.level === 'warning' ? 'warning' : 'info'" size="small">
            {{ platformLabels[issue.platform] }}
          </el-tag>
          <span>{{ issue.field }}：{{ issue.message }}</span>
        </li>
      </ul>
    </div>

    <footer class="confirm-actions">
      <el-button @click="$emit('back')">返回预览</el-button>
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

.mode-group,
.platforms {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
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
