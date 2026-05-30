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
  Notebook,
  Refresh,
  VideoCamera
} from "@element-plus/icons-vue";

import {
  connectWechatAccount,
  deleteAccount,
  getAccounts,
  getBilibiliCaptcha,
  loginBilibili,
  testAccountConnection,
  type AccountConnection,
  type BilibiliLoginPayload,
  type PlatformKey,
  type WechatConnectPayload
} from "@/api/client";

type AccountStatus = "connected" | "disconnected" | "placeholder" | "error";
type SupportedPlatform = PlatformKey;

interface GeetestValidation {
  geetest_challenge: string;
  geetest_validate: string;
  geetest_seccode: string;
}

interface GeetestInstance {
  appendTo: (element: HTMLElement | string) => void;
  getValidate: () => GeetestValidation | false;
  onReady: (callback: () => void) => void;
  onSuccess: (callback: () => void) => void;
  onError: (callback: () => void) => void;
  reset: () => void;
}

declare global {
  interface Window {
    initGeetest?: (config: Record<string, unknown>, callback: (captcha: GeetestInstance) => void) => void;
  }
}

interface PlatformConfig {
  key: SupportedPlatform;
  label: string;
  authType: string;
  icon: typeof Document;
  status: AccountStatus;
  note: string;
  username: string;
  disabled?: boolean;
  loginResult?: string;
  account?: AccountConnection;
}

const wechatFormRef = ref<FormInstance>();
const bilibiliFormRef = ref<FormInstance>();
const bilibiliCaptchaRef = ref<HTMLElement>();
const bilibiliCaptchaInstance = ref<GeetestInstance | null>(null);
const loadingAction = ref<string>("");
const loadError = ref("");

let geetestScriptPromise: Promise<void> | null = null;

const wechatForm = reactive<WechatConnectPayload>({
  app_id: "",
  app_secret: "",
  display_name: "公众号"
});

const bilibiliForm = reactive<BilibiliLoginPayload>({
  username: "",
  password: "",
  token: "",
  challenge: "",
  validate: "",
  seccode: "",
  display_name: "B站账号"
});

const bilibiliCaptchaState = reactive({
  ready: false,
  verified: false,
  message: "尚未获取验证码"
});

const bilibiliLoginState = reactive({
  message: "",
  type: "info" as "info" | "success" | "warning" | "danger"
});

const wechatRules: FormRules<WechatConnectPayload> = {
  app_id: [{ required: true, message: "请输入 AppID", trigger: "blur" }],
  app_secret: [{ required: true, message: "请输入 AppSecret", trigger: "blur" }]
};

const bilibiliRules: FormRules<BilibiliLoginPayload> = {
  username: [{ required: true, message: "请输入 B站账号", trigger: "blur" }],
  password: [{ required: true, message: "请输入 B站密码", trigger: "blur" }]
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
    authType: "用户名密码",
    icon: VideoCamera,
    status: "disconnected",
    note: "等待登录",
    username: "未登录"
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

function setWechatFormRef(instance: unknown) {
  if (instance) {
    wechatFormRef.value = instance as FormInstance;
  }
}

function setBilibiliFormRef(instance: unknown) {
  if (instance) {
    bilibiliFormRef.value = instance as FormInstance;
  }
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

function toLocalStatus(account: AccountConnection): AccountStatus {
  if (account.status === "connected") {
    return "connected";
  }
  if (account.status === "error" || account.status === "expired") {
    return "error";
  }
  return "disconnected";
}

function applyAccounts(accounts: AccountConnection[]) {
  for (const account of accounts) {
    const platform = platformByKey(account.platform);
    if (!platform || platform.disabled) {
      continue;
    }

    platform.account = account;
    platform.status = toLocalStatus(account);
    platform.note = account.message || (account.status === "connected" ? "已完成配置" : "尚未连接");
    platform.username = account.status === "connected" ? account.display_name : platform.key === "bilibili" ? "未登录" : "未配置";
  }
}

function resetBilibiliCaptcha() {
  bilibiliCaptchaInstance.value = null;
  bilibiliCaptchaState.ready = false;
  bilibiliCaptchaState.verified = false;
  bilibiliCaptchaState.message = "尚未获取验证码";
  bilibiliForm.token = "";
  bilibiliForm.challenge = "";
  bilibiliForm.validate = "";
  bilibiliForm.seccode = "";
  if (bilibiliCaptchaRef.value) {
    bilibiliCaptchaRef.value.innerHTML = "";
  }
}

function loadGeetestSdk(): Promise<void> {
  if (window.initGeetest) {
    return Promise.resolve();
  }

  if (geetestScriptPromise) {
    return geetestScriptPromise;
  }

  geetestScriptPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://static.geetest.com/static/tools/gt.js";
    script.async = true;
    script.onload = () => {
      if (window.initGeetest) {
        resolve();
      } else {
        reject(new Error("极验组件加载失败"));
      }
    };
    script.onerror = () => reject(new Error("极验组件加载失败"));
    document.head.appendChild(script);
  });

  return geetestScriptPromise;
}

async function initializeBilibiliCaptcha() {
  loadingAction.value = "bilibili-captcha";
  resetBilibiliCaptcha();

  try {
    const captcha = await getBilibiliCaptcha();
    bilibiliForm.token = captcha.token;
    bilibiliForm.challenge = captcha.challenge;
    await loadGeetestSdk();

    if (!window.initGeetest || !bilibiliCaptchaRef.value) {
      throw new Error("极验组件暂不可用");
    }

    window.initGeetest(
      {
        gt: captcha.gt,
        challenge: captcha.challenge,
        offline: false,
        new_captcha: true,
        product: "float",
        width: "100%"
      },
      (captchaInstance) => {
        bilibiliCaptchaInstance.value = captchaInstance;
        captchaInstance.appendTo(bilibiliCaptchaRef.value as HTMLElement);
        captchaInstance.onReady(() => {
          bilibiliCaptchaState.ready = true;
          bilibiliCaptchaState.message = "请完成验证码";
        });
        captchaInstance.onSuccess(() => {
          const result = captchaInstance.getValidate();
          if (!result) {
            bilibiliCaptchaState.verified = false;
            bilibiliCaptchaState.message = "验证码结果为空";
            return;
          }
          bilibiliForm.challenge = result.geetest_challenge;
          bilibiliForm.validate = result.geetest_validate;
          bilibiliForm.seccode = result.geetest_seccode;
          bilibiliCaptchaState.verified = true;
          bilibiliCaptchaState.message = "验证码已通过";
        });
        captchaInstance.onError(() => {
          bilibiliCaptchaState.verified = false;
          bilibiliCaptchaState.message = "验证码加载异常";
        });
      }
    );
  } catch (error) {
    bilibiliCaptchaState.message = error instanceof Error ? error.message : "验证码获取失败";
    ElMessage.error(bilibiliCaptchaState.message);
  } finally {
    loadingAction.value = "";
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
  if (!wechatFormRef.value) {
    ElMessage.error("公众号表单尚未初始化，请重新打开配置面板");
    return;
  }

  const valid = await wechatFormRef.value.validate().catch(() => false);
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

async function connectBilibili() {
  bilibiliLoginState.message = "正在校验登录表单...";
  bilibiliLoginState.type = "info";

  if (!bilibiliFormRef.value) {
    bilibiliLoginState.message = "B站登录表单尚未初始化，请重新打开登录面板";
    bilibiliLoginState.type = "danger";
    ElMessage.error(bilibiliLoginState.message);
    return;
  }

  const valid = await bilibiliFormRef.value.validate().catch(() => false);
  if (!valid) {
    bilibiliLoginState.message = "请先填写 B站账号和密码";
    bilibiliLoginState.type = "warning";
    return;
  }

  if (!bilibiliCaptchaState.verified) {
    bilibiliLoginState.message = "请先获取并完成 B站验证码";
    bilibiliLoginState.type = "warning";
    ElMessage.warning(bilibiliLoginState.message);
    return;
  }

  loadingAction.value = "bilibili-login";
  bilibiliLoginState.message = "正在提交 B站登录...";
  bilibiliLoginState.type = "info";

  try {
    const result = await loginBilibili({
      ...bilibiliForm,
      display_name: bilibiliForm.display_name?.trim() || undefined
    });
    const platform = platformByKey("bilibili");
    applyAccounts([result.account]);
    if (platform) {
      platform.loginResult = result.message;
      platform.note = result.message;
    }
    bilibiliLoginState.message = result.message;
    bilibiliLoginState.type = "success";
    bilibiliForm.password = "";
    resetBilibiliCaptcha();
    ElMessage.success(result.message);
  } catch (error) {
    const message = error instanceof Error ? error.message : "B站登录失败";
    const platform = platformByKey("bilibili");
    if (platform) {
      platform.status = "error";
      platform.loginResult = message;
      platform.note = "B站登录失败";
    }
    bilibiliLoginState.message = message;
    bilibiliLoginState.type = "danger";
    resetBilibiliCaptcha();
    bilibiliCaptchaState.message = "登录失败，请重新获取验证码";
    ElMessage.error(message);
  } finally {
    loadingAction.value = "";
  }
}

async function testConnection(platformKey: SupportedPlatform) {
  loadingAction.value = `${platformKey}-test`;

  try {
    const result = await testAccountConnection(platformKey);
    applyAccounts([result.account]);
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
  const platform = platformByKey(platformKey);
  const accountId = platform?.account?.account_id;
  if (!accountId) {
    ElMessage.warning("当前平台尚未连接账号");
    return;
  }

  loadingAction.value = `${platformKey}-disconnect`;

  try {
    await deleteAccount(accountId);
    platform.account = undefined;
    platform.status = "disconnected";
    platform.note = platformKey === "bilibili" ? "等待登录" : "尚未连接";
    platform.username = platformKey === "bilibili" ? "未登录" : "未配置";
    platform.loginResult = "";
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

            <el-form :ref="setWechatFormRef" class="account-form" :model="wechatForm" :rules="wechatRules" label-position="top">
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

          <el-popover v-if="platform.key === 'bilibili'" placement="bottom-end" :width="420" trigger="click">
            <template #reference>
              <el-button
                type="primary"
                :icon="Key"
                :loading="loadingAction === 'bilibili-login'"
                :disabled="isBusy && loadingAction !== 'bilibili-login'"
              >
                登录
              </el-button>
            </template>

            <el-form :ref="setBilibiliFormRef" class="account-form" :model="bilibiliForm" :rules="bilibiliRules" label-position="top">
              <el-form-item label="账号显示名" prop="display_name">
                <el-input v-model="bilibiliForm.display_name" placeholder="例如：运营号" />
              </el-form-item>
              <el-form-item label="B站账号" prop="username">
                <el-input v-model="bilibiliForm.username" autocomplete="username" placeholder="手机号或邮箱">
                  <template #prefix>
                    <el-icon><Key /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item label="B站密码" prop="password">
                <el-input v-model="bilibiliForm.password" type="password" show-password autocomplete="current-password" placeholder="请输入密码">
                  <template #prefix>
                    <el-icon><Key /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item label="极验验证码">
                <div class="captcha-panel">
                  <div ref="bilibiliCaptchaRef" class="captcha-box"></div>
                  <div class="captcha-actions">
                    <el-button
                      size="small"
                      :loading="loadingAction === 'bilibili-captcha'"
                      :disabled="isBusy && loadingAction !== 'bilibili-captcha'"
                      @click="initializeBilibiliCaptcha"
                    >
                      {{ bilibiliCaptchaState.ready ? "刷新验证码" : "获取验证码" }}
                    </el-button>
                    <span :class="['captcha-status', { verified: bilibiliCaptchaState.verified }]">
                      {{ bilibiliCaptchaState.message }}
                    </span>
                  </div>
                </div>
              </el-form-item>
              <div v-if="bilibiliLoginState.message || platform.loginResult" :class="['login-result', bilibiliLoginState.type]">
                {{ bilibiliLoginState.message || platform.loginResult }}
              </div>
              <el-button
                type="primary"
                :loading="loadingAction === 'bilibili-login'"
                :disabled="isBusy && loadingAction !== 'bilibili-login'"
                @click="connectBilibili"
              >
                保存登录
              </el-button>
            </el-form>
          </el-popover>

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

.captcha-panel,
.captcha-box {
  width: 100%;
  min-width: 0;
}

.captcha-box {
  min-height: 42px;
}

.captcha-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}

.captcha-status,
.login-result {
  color: #607086;
  font-size: 12px;
  line-height: 1.45;
  word-break: break-word;
}

.captcha-status.verified {
  color: #2f8f4e;
}

.login-result {
  margin-bottom: 10px;
}

.login-result.success {
  color: #2f8f4e;
}

.login-result.warning {
  color: #b7791f;
}

.login-result.danger {
  color: #c2413a;
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
