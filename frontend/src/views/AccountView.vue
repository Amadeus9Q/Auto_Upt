<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import {
  ChatDotRound,
  CircleCheck,
  CircleClose,
  Connection,
  Document,
  Key,
  Link,
  Notebook,
  Refresh,
  VideoCamera
} from "@element-plus/icons-vue";

import {
  connectWechatAccount,
  deleteAccount,
  getAccounts,
  startBilibiliOAuth,
  testAccountConnection,
  type AccountConnection,
  type PlatformKey,
  type WechatConnectPayload
} from "@/api/client";

type AccountStatus = "connected" | "disconnected" | "placeholder" | "error";
type SupportedPlatform = PlatformKey;

interface PlatformConfig {
  key: SupportedPlatform;
  label: string;
  authType: string;
  icon: typeof Document;
  status: AccountStatus;
  note: string;
  username: string;
  disabled?: boolean;
  callbackResult?: string;
  account?: AccountConnection;
}

const wechatFormRef = ref<FormInstance>();
const loadingAction = ref<string>("");
const loadError = ref("");

const wechatForm = reactive<WechatConnectPayload>({
  app_id: "",
  app_secret: "",
  display_name: "公众号"
});

const wechatRules: FormRules<WechatConnectPayload> = {
  app_id: [{ required: true, message: "请输入 AppID", trigger: "blur" }],
  app_secret: [{ required: true, message: "请输入 AppSecret", trigger: "blur" }]
};

const platforms = reactive<PlatformConfig[]>([
  {
    key: "wechat",
    label: "公众号",
    authType: "AppID / AppSecret",
    icon: Document,
    status: "disconnected",
    note: "尚未连接",
    username: "未配置"
  },
  {
    key: "bilibili",
    label: "B站",
    authType: "OAuth",
    icon: VideoCamera,
    status: "disconnected",
    note: "等待授权",
    username: "未授权"
  },
  {
    key: "zhihu",
    label: "知乎",
    authType: "第三阶段",
    icon: ChatDotRound,
    status: "placeholder",
    note: "第三阶段浏览器辅助发布接入",
    username: "暂未接入",
    disabled: true
  },
  {
    key: "xiaohongshu",
    label: "小红书",
    authType: "第三阶段",
    icon: Notebook,
    status: "placeholder",
    note: "第三阶段浏览器辅助发布接入",
    username: "暂未接入",
    disabled: true
  }
]);

const isBusy = computed(() => Boolean(loadingAction.value));

function platformByKey(platform: SupportedPlatform) {
  return platforms.find((item) => item.key === platform);
}

function statusMeta(status: AccountStatus) {
  const meta = {
    connected: { label: "已连接", type: "success" as const, icon: CircleCheck },
    disconnected: { label: "未连接", type: "info" as const, icon: CircleClose },
    placeholder: { label: "后续接入", type: "warning" as const, icon: Refresh },
    error: { label: "异常", type: "danger" as const, icon: CircleClose }
  };

  return meta[status];
}

function formatExpireTime(value?: string | null) {
  if (!value) {
    return "未返回";
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN");
}

function applyAccounts(accounts: AccountConnection[]) {
  for (const account of accounts) {
    const platform = platformByKey(account.platform);
    if (!platform) {
      continue;
    }

    platform.account = account;
    platform.status = account.status === "connected" ? "connected" : "disconnected";
    platform.note = account.display_name || (account.status === "connected" ? "已完成配置" : "尚未连接");
    platform.username = account.display_name || platform.username;
  }
}

async function refreshAccounts(showToast = false) {
  loadingAction.value = "refresh";
  loadError.value = "";

  try {
    const accounts = await getAccounts();
    applyAccounts(accounts);
    if (showToast) {
      ElMessage.success("账号状态已刷新");
    }
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : "账号状态刷新失败";
    if (showToast) {
      ElMessage.error("账号接口暂不可用");
    }
  } finally {
    loadingAction.value = "";
  }
}

async function connectWechat() {
  const valid = await wechatFormRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }

  loadingAction.value = "wechat-connect";

  try {
    const account = await connectWechatAccount({ ...wechatForm });
    applyAccounts([account]);
    ElMessage.success("公众号配置已保存");
  } catch (error) {
    const platform = platformByKey("wechat");
    if (platform) {
      platform.status = "error";
      platform.note = "连接接口未完成或配置校验失败";
    }
    ElMessage.error(error instanceof Error ? error.message : "公众号连接失败");
  } finally {
    loadingAction.value = "";
  }
}

async function authorizeBilibili() {
  loadingAction.value = "bilibili-oauth";

  try {
    const result = await startBilibiliOAuth();
    const platform = platformByKey("bilibili");
    if (platform) {
      platform.callbackResult = result.callback_message ?? "已获取授权地址，等待回调结果";
      platform.note = "授权流程已启动";
    }

    if (result.authorization_url) {
      window.location.assign(result.authorization_url);
      return;
    }

    ElMessage.success("B站授权流程已启动");
  } catch (error) {
    const platform = platformByKey("bilibili");
    if (platform) {
      platform.status = "error";
      platform.callbackResult = error instanceof Error ? error.message : "授权启动失败";
      platform.note = "授权接口暂不可用";
    }
    ElMessage.error("B站授权启动失败");
  } finally {
    loadingAction.value = "";
  }
}

async function testConnection(platformKey: SupportedPlatform) {
  loadingAction.value = `${platformKey}-test`;

  try {
    const result = await testAccountConnection(platformKey);
    const platform = platformByKey(platformKey);
    if (platform) {
      platform.status = result.ok ? "connected" : "error";
      platform.note = result.message;
    }
    ElMessage[result.ok ? "success" : "warning"](result.message);
  } catch (error) {
    const platform = platformByKey(platformKey);
    if (platform) {
      platform.status = "error";
      platform.note = "连接测试接口暂不可用";
    }
    ElMessage.error(error instanceof Error ? error.message : "连接测试失败");
  } finally {
    loadingAction.value = "";
  }
}

async function disconnect(platformKey: SupportedPlatform) {
  loadingAction.value = `${platformKey}-disconnect`;

  try {
    await deleteAccount(platformKey);
    const platform = platformByKey(platformKey);
    if (platform) {
      platform.account = undefined;
      platform.status = "disconnected";
      platform.note = platformKey === "bilibili" ? "等待授权" : "尚未连接";
      platform.username = platformKey === "bilibili" ? "未授权" : "未配置";
      platform.callbackResult = "";
    }
    ElMessage.success("已断开连接");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "断开连接失败");
  } finally {
    loadingAction.value = "";
  }
}

void refreshAccounts();
</script>

<template>
  <section class="account-view">
    <div class="section-title">
      <div>
        <p>账号管理</p>
        <h2>B站与公众号真实发布接入准备</h2>
      </div>
      <el-button :icon="Refresh" :loading="loadingAction === 'refresh'" @click="refreshAccounts(true)">刷新状态</el-button>
    </div>

    <el-alert
      v-if="loadError"
      class="phase-note"
      :title="`账号接口暂未就绪：${loadError}`"
      type="warning"
      show-icon
      :closable="false"
    />

    <div class="account-table">
      <div class="account-table-head">
        <span>平台</span>
        <span>用户名称</span>
        <span>状态</span>
        <span>操作</span>
      </div>

      <article v-for="platform in platforms" :key="platform.key" class="account-row">
        <div class="platform-cell">
          <span class="account-icon">
            <el-icon :size="22">
              <component :is="platform.icon" />
            </el-icon>
          </span>
          <span>
            <strong>{{ platform.label }}</strong>
            <small>{{ platform.authType }}</small>
          </span>
        </div>

        <div class="username-cell">
          <strong>{{ platform.username }}</strong>
          <small v-if="platform.account?.token_expires_at">Token 过期：{{ formatExpireTime(platform.account.token_expires_at) }}</small>
        </div>

        <div class="status-cell">
          <el-tag :type="statusMeta(platform.status).type">
            <el-icon>
              <component :is="statusMeta(platform.status).icon" />
            </el-icon>
            {{ statusMeta(platform.status).label }}
          </el-tag>
          <small>{{ platform.note }}</small>
        </div>

        <div class="actions-cell">
          <el-popover v-if="platform.key === 'wechat'" placement="bottom-end" :width="360" trigger="click">
            <template #reference>
              <el-button :icon="Connection" type="primary">配置</el-button>
            </template>

            <el-form ref="wechatFormRef" class="account-form" :model="wechatForm" :rules="wechatRules" label-position="top">
              <el-form-item label="账号显示名" prop="display_name">
                <el-input v-model="wechatForm.display_name" placeholder="例如：品牌服务号" />
              </el-form-item>
              <el-form-item label="AppID" prop="app_id">
                <el-input v-model="wechatForm.app_id" autocomplete="off" placeholder="请输入公众号 AppID">
                  <template #prefix>
                    <el-icon><Key /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item label="AppSecret" prop="app_secret">
                <el-input v-model="wechatForm.app_secret" type="password" show-password autocomplete="new-password" placeholder="请输入 AppSecret">
                  <template #prefix>
                    <el-icon><Key /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-button
                type="primary"
                :loading="loadingAction === 'wechat-connect'"
                :disabled="isBusy && loadingAction !== 'wechat-connect'"
                @click="connectWechat"
              >
                保存配置
              </el-button>
            </el-form>
          </el-popover>

          <template v-if="platform.key === 'bilibili'">
            <el-button
              type="primary"
              :icon="Link"
              :loading="loadingAction === 'bilibili-oauth'"
              :disabled="isBusy && loadingAction !== 'bilibili-oauth'"
              @click="authorizeBilibili"
            >
              开始授权
            </el-button>
            <el-popover placement="bottom-end" :width="320" trigger="click">
              <template #reference>
                <el-button>回调结果</el-button>
              </template>
              <div class="callback-result">
                <span>授权回调结果</span>
                <p>{{ platform.callbackResult || platform.account?.display_name || "尚未收到回调结果" }}</p>
              </div>
            </el-popover>
          </template>

          <el-tag v-if="platform.disabled" type="info">第三阶段浏览器辅助发布接入</el-tag>

          <el-button
            v-if="!platform.disabled"
            :loading="loadingAction === `${platform.key}-test`"
            :disabled="isBusy && loadingAction !== `${platform.key}-test`"
            @click="testConnection(platform.key)"
          >
            连接测试
          </el-button>
          <el-button
            v-if="!platform.disabled"
            type="danger"
            plain
            :loading="loadingAction === `${platform.key}-disconnect`"
            :disabled="isBusy && loadingAction !== `${platform.key}-disconnect`"
            @click="disconnect(platform.key)"
          >
            断开连接
          </el-button>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.account-view {
  min-width: 0;
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

.account-table {
  background: #ffffff;
  border: 1px solid #dfe5ee;
  border-radius: 8px;
  overflow: hidden;
}

.account-table-head,
.account-row {
  display: grid;
  grid-template-columns: minmax(160px, 0.8fr) minmax(140px, 0.8fr) minmax(180px, 1fr) minmax(320px, 1.4fr);
  align-items: center;
  gap: 16px;
}

.account-table-head {
  padding: 12px 18px;
  color: #607086;
  background: #f7f9fc;
  border-bottom: 1px solid #e7edf5;
  font-size: 13px;
  font-weight: 600;
}

.account-row {
  min-width: 0;
  padding: 16px 18px;
  border-bottom: 1px solid #edf1f6;
}

.account-row:last-child {
  border-bottom: 0;
}

.platform-cell,
.username-cell,
.status-cell,
.actions-cell {
  min-width: 0;
}

.platform-cell,
.actions-cell {
  display: flex;
  align-items: center;
}

.platform-cell {
  gap: 12px;
}

.platform-cell strong,
.platform-cell small,
.username-cell strong,
.username-cell small,
.status-cell small {
  display: block;
}

.platform-cell strong,
.username-cell strong {
  color: #172033;
  font-size: 15px;
}

.platform-cell small,
.username-cell small,
.status-cell small {
  margin-top: 4px;
  color: #607086;
  font-size: 12px;
}

.account-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  flex: 0 0 auto;
  color: #1f6feb;
  background: #edf4ff;
  border-radius: 8px;
}

.callback-result {
  min-width: 0;
}

.callback-result span {
  color: #718096;
  font-size: 12px;
}

.callback-result p {
  margin: 5px 0 0;
  color: #172033;
  font-size: 13px;
  line-height: 1.45;
  word-break: break-word;
}

.actions-cell {
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.phase-note {
  margin-bottom: 18px;
}

@media (max-width: 1120px) {
  .account-table-head {
    display: none;
  }

  .account-row {
    grid-template-columns: 1fr;
    align-items: flex-start;
    gap: 12px;
  }

  .actions-cell {
    justify-content: flex-start;
  }
}

@media (max-width: 560px) {
  .section-title {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
