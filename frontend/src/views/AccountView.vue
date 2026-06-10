<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus";
import {
  ArrowDown,
  ChatDotRound,
  Close,
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
  revealAccountSecret,
  testAccountConnection,
  type AccountConnection,
  type BilibiliLoginPayload,
  type PlatformKey,
  type SavedCredentialOption,
  type WechatConnectPayload
} from "@/api/client";
import { getErrorMessage } from "@/utils/errors";

type AccountStatus = "connected" | "disconnected" | "placeholder" | "error";
type SupportedPlatform = PlatformKey;

const props = withDefaults(defineProps<{
  focusedPlatform?: PlatformKey | null;
  autoOpenConfig?: boolean;
  compact?: boolean;
  configurationOnly?: boolean;
  initialAccounts?: AccountConnection[];
}>(), {
  focusedPlatform: null,
  autoOpenConfig: false,
  compact: false,
  configurationOnly: false,
  initialAccounts: () => []
});

const emit = defineEmits<{
  accountUpdated: [account: AccountConnection];
}>();

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
const wechatSavedCredentials = ref<SavedCredentialOption[]>([]);
const wechatSelectVersion = ref(0);
const wechatConfigVisible = ref(false);
const bilibiliConfigVisible = ref(false);

let geetestScriptPromise: Promise<void> | null = null;
let accountStateVersion = 0;

const wechatForm = reactive<WechatConnectPayload>({
  app_id: "",
  app_secret: "",
  account_id: null
});

const bilibiliForm = reactive<BilibiliLoginPayload>({
  username: "",
  password: "",
  token: "",
  challenge: "",
  validate: "",
  seccode: ""
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
  app_secret: [{ validator: validateWechatSecret, trigger: "blur" }]
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
const wechatCredentialOptions = computed(() => [...wechatSavedCredentials.value]);
const visiblePlatforms = computed(() =>
  props.focusedPlatform
    ? platforms.filter((platform) => platform.key === props.focusedPlatform)
    : platforms
);

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

function isBeforeExpiry(value?: string | null) {
  if (!value) {
    return true;
  }

  const expiresAt = new Date(value).getTime();
  return Number.isNaN(expiresAt) ? true : expiresAt > Date.now();
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

function validateWechatSecret(_rule: unknown, value: string | null | undefined, callback: (error?: Error) => void) {
  if (value?.trim()) {
    callback();
    return;
  }
  callback(new Error("请输入 AppSecret，或从历史 AppID 中选择已保存凭据。"));
}

function findWechatCredential(appId: string) {
  return wechatSavedCredentials.value.find((item) => item.app_id === appId);
}

function queryWechatCredentials(query: string, callback: (items: SavedCredentialOption[]) => void) {
  const normalizedQuery = query.trim().toLowerCase();
  callback(
    normalizedQuery
      ? wechatCredentialOptions.value.filter((item) => item.app_id.toLowerCase().includes(normalizedQuery))
      : wechatCredentialOptions.value
  );
}

async function selectWechatCredential(option: SavedCredentialOption) {
  wechatForm.app_id = option.app_id;
  wechatForm.account_id = option.account_id;
  wechatForm.app_secret = "";
  if (!option.has_secret) {
    return;
  }

  loadingAction.value = `wechat-reveal-${option.account_id}`;
  try {
    const revealed = await revealAccountSecret(option.account_id);
    wechatForm.app_secret = revealed.app_secret;
    void wechatFormRef.value?.clearValidate?.("app_secret");
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "读取 AppSecret 失败"));
  } finally {
    loadingAction.value = "";
  }
}

function clearWechatCredentialSelection() {
  wechatForm.app_id = "";
  detachWechatCredential();
  void nextTick(() => {
    wechatSelectVersion.value += 1;
  });
}

function detachWechatCredential() {
  wechatForm.account_id = null;
  wechatForm.app_secret = "";
  void wechatFormRef.value?.clearValidate?.();
}

function handleWechatAppIdInput(value: string) {
  wechatForm.app_id = value;
  const option = findWechatCredential(value);
  if (option) {
    void selectWechatCredential(option);
    return;
  }
  detachWechatCredential();
}

function handleWechatAppIdBlur() {
  wechatForm.app_id = wechatForm.app_id.trim();
  handleWechatAppIdInput(wechatForm.app_id);
}

function syncWechatForm(account: AccountConnection) {
  wechatSavedCredentials.value = account.saved_credentials ?? [];
  const usableSavedCredential = account.status === "connected" && isBeforeExpiry(account.token_expires_at);
  if (!usableSavedCredential) {
    wechatForm.app_id = "";
    wechatForm.app_secret = "";
    wechatForm.account_id = null;
    return;
  }

  const option = wechatSavedCredentials.value.find(
    (item) => item.is_active || item.account_id === account.account_id || item.app_id === account.external_user_id
  );
  if (option) {
    void selectWechatCredential(option);
    return;
  }

  wechatForm.app_id = account.external_user_id ?? "";
  wechatForm.account_id = account.account_id;
  wechatForm.app_secret = "";
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
    platform.username = account.status === "connected"
      ? (account.platform === "wechat" ? account.external_user_id || account.display_name : account.display_name)
      : platform.key === "bilibili" ? "未登录" : "未配置";

    if (account.platform === "wechat") {
      syncWechatForm(account);
    }
  }
}

watch(
  () => props.initialAccounts,
  (accounts) => {
    if (accounts.length) {
      applyAccounts(accounts);
    }
  },
  { immediate: true }
);

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
    bilibiliCaptchaState.message = getErrorMessage(error, "验证码获取失败");
    ElMessage.error(bilibiliCaptchaState.message);
  } finally {
    loadingAction.value = "";
  }
}

async function refreshAccounts(showToast = false) {
  const requestedAtVersion = accountStateVersion;
  loadingAction.value = "refresh";
  loadError.value = "";

  try {
    const accounts = await getAccounts();
    if (requestedAtVersion !== accountStateVersion) {
      return;
    }
    applyAccounts(accounts);
    if (showToast) {
      ElMessage.success("账号状态已刷新");
    }
  } catch (error) {
    loadError.value = getErrorMessage(error, "账号状态刷新失败");
    if (showToast) {
      ElMessage.error("暂时无法读取账号状态");
    }
  } finally {
    if (loadingAction.value === "refresh") {
      loadingAction.value = "";
    }
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
    const appSecret = wechatForm.app_secret?.trim() ?? "";
    const account = await connectWechatAccount({
      app_id: wechatForm.app_id.trim(),
      app_secret: appSecret || null,
      account_id: wechatForm.account_id ?? null
    });
    accountStateVersion += 1;
    applyAccounts([account]);
    emit("accountUpdated", account);
    ElMessage.success("公众号登录成功");
  } catch (error) {
    const platform = platformByKey("wechat");
    if (platform) {
      platform.status = "error";
      platform.note = "连接接口未完成或配置校验失败";
    }
    ElMessage.error(getErrorMessage(error, "公众号连接失败"));
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
      username: bilibiliForm.username,
      password: bilibiliForm.password,
      token: bilibiliForm.token,
      challenge: bilibiliForm.challenge,
      validate: bilibiliForm.validate,
      seccode: bilibiliForm.seccode
    });
    const platform = platformByKey("bilibili");
    accountStateVersion += 1;
    applyAccounts([result.account]);
    emit("accountUpdated", result.account);
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
    const message = getErrorMessage(error, "B站登录失败");
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
    accountStateVersion += 1;
    applyAccounts([result.account]);
    emit("accountUpdated", result.account);
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
      platform.note = "当前暂时无法测试连接";
    }
    ElMessage.error(getErrorMessage(error, "连接测试失败"));
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
    const account = await deleteAccount(accountId);
    accountStateVersion += 1;
    emit("accountUpdated", account);
    platform.account = undefined;
    platform.status = "disconnected";
    platform.note = platformKey === "bilibili" ? "等待登录" : "尚未连接";
    platform.username = platformKey === "bilibili" ? "未登录" : "未配置";
    platform.loginResult = "";
    if (platformKey === "wechat") {
      wechatForm.app_id = "";
      wechatForm.app_secret = "";
      wechatForm.account_id = null;
      wechatSavedCredentials.value = wechatSavedCredentials.value.filter((item) => item.account_id !== accountId);
    }
    ElMessage.success("已断开连接");
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "断开连接失败"));
  } finally {
    loadingAction.value = "";
  }
}

async function deleteWechatCredential(credential: SavedCredentialOption, event: MouseEvent) {
  event.preventDefault();
  event.stopPropagation();

  try {
    await ElMessageBox.confirm(
      `确认清除已保存的公众号账号记录 ${credential.app_id}？清除后需要重新输入 AppSecret 才能再次使用。`,
      "清除账号记录",
      {
        confirmButtonText: "确认清除",
        cancelButtonText: "取消",
        type: "warning"
      }
    );
  } catch {
    return;
  }

  loadingAction.value = `wechat-delete-${credential.account_id}`;
  try {
    const account = await deleteAccount(credential.account_id);
    accountStateVersion += 1;
    emit("accountUpdated", account);
    wechatSavedCredentials.value = wechatSavedCredentials.value.filter((item) => item.account_id !== credential.account_id);
    const platform = platformByKey("wechat");
    const deletedActive = credential.is_active || platform?.account?.account_id === credential.account_id;
    const deletedSelected = wechatForm.account_id === credential.account_id;
    if (deletedSelected) {
      wechatForm.app_id = "";
      wechatForm.app_secret = "";
      wechatForm.account_id = null;
    }
    if (deletedActive && platform) {
      platform.account = undefined;
      platform.status = "disconnected";
      platform.note = "尚未连接";
      platform.username = "未配置";
    }
    ElMessage.success("已删除账号");
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "删除账号失败"));
  } finally {
    loadingAction.value = "";
  }
}

onMounted(async () => {
  void refreshAccounts();
  if (!props.autoOpenConfig) {
    return;
  }
  await nextTick();
  wechatConfigVisible.value = props.focusedPlatform === "wechat";
  bilibiliConfigVisible.value = props.focusedPlatform === "bilibili";
});
</script>

<template>
  <section class="account-view" :class="{ 'is-compact': compact }">
    <div v-if="!compact && !configurationOnly" class="section-title">
      <div>
        <h2>平台授权状态</h2>
      </div>
      <el-button :icon="Refresh" :loading="loadingAction === 'refresh'" @click="refreshAccounts(true)">刷新状态</el-button>
    </div>

    <el-alert
      v-if="loadError && !configurationOnly"
      class="phase-note"
      :title="`暂时无法读取账号状态：${loadError}`"
      type="warning"
      show-icon
      :closable="false"
    />

    <div v-if="configurationOnly" class="direct-config-panel">
      <el-form
        v-if="focusedPlatform === 'wechat'"
        :ref="setWechatFormRef"
        class="account-form"
        :model="wechatForm"
        :rules="wechatRules"
        label-position="right"
        label-width="88px"
      >
        <el-form-item label="AppID" prop="app_id">
          <el-autocomplete
            :key="`direct-wechat-select-${wechatSelectVersion}`"
            v-model="wechatForm.app_id"
            clearable
            value-key="app_id"
            :fetch-suggestions="queryWechatCredentials"
            placeholder="输入或选择公众号 AppID"
            @input="handleWechatAppIdInput"
            @select="selectWechatCredential"
            @blur="handleWechatAppIdBlur"
            @clear="clearWechatCredentialSelection"
          >
            <template #suffix>
              <el-icon class="credential-dropdown-icon"><ArrowDown /></el-icon>
            </template>
            <template #default="{ item: credential }">
              <div class="credential-option">
                <span>{{ credential.app_id }}</span>
                <el-button
                  class="credential-delete"
                  text
                  circle
                  :icon="Close"
                  :loading="loadingAction === `wechat-delete-${credential.account_id}`"
                  aria-label="清除已保存账号记录"
                  title="清除已保存账号记录"
                  @click="deleteWechatCredential(credential, $event)"
                />
              </div>
            </template>
          </el-autocomplete>
        </el-form-item>
        <el-form-item label="AppSecret" prop="app_secret">
          <el-input v-model="wechatForm.app_secret" type="password" show-password autocomplete="new-password" placeholder="请输入 AppSecret">
            <template #prefix>
              <el-icon><Key /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <div class="direct-config-actions">
          <el-button
            type="primary"
            :loading="loadingAction === 'wechat-connect'"
            :disabled="isBusy && loadingAction !== 'wechat-connect'"
            @click="connectWechat"
          >
            保存配置
          </el-button>
        </div>
      </el-form>

      <el-form
        v-else-if="focusedPlatform === 'bilibili'"
        :ref="setBilibiliFormRef"
        class="account-form"
        :model="bilibiliForm"
        :rules="bilibiliRules"
        label-position="right"
        label-width="88px"
      >
        <el-form-item label="B 站账号" prop="username">
          <el-input v-model="bilibiliForm.username" autocomplete="username" placeholder="手机号或邮箱">
            <template #prefix>
              <el-icon><Key /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="B 站密码" prop="password">
          <el-input v-model="bilibiliForm.password" type="password" show-password autocomplete="current-password" placeholder="请输入密码">
            <template #prefix>
              <el-icon><Key /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="验证码">
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
        <div v-if="bilibiliLoginState.message" :class="['login-result', bilibiliLoginState.type]">
          {{ bilibiliLoginState.message }}
        </div>
        <div class="direct-config-actions">
          <el-button
            type="primary"
            :loading="loadingAction === 'bilibili-login'"
            :disabled="isBusy && loadingAction !== 'bilibili-login'"
            @click="connectBilibili"
          >
            保存登录
          </el-button>
        </div>
      </el-form>
    </div>

    <div v-else class="account-table">
      <div v-if="!compact" class="account-table-head">
        <span>平台</span>
        <span>用户名称</span>
        <span>状态</span>
        <span>操作</span>
      </div>

      <article v-for="platform in visiblePlatforms" :key="platform.key" class="account-row">
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
          <el-popover v-if="platform.key === 'wechat'" v-model:visible="wechatConfigVisible" placement="bottom-end" :width="360" trigger="click">
            <template #reference>
              <el-button :icon="Connection" type="primary">配置</el-button>
            </template>

            <el-form :ref="setWechatFormRef" class="account-form" :model="wechatForm" :rules="wechatRules" label-position="top">
              <div class="form-head">
                <span>公众号账号</span>
                <el-button text circle :icon="Close" @click="wechatConfigVisible = false" />
              </div>
              <el-form-item label="AppID" prop="app_id">
                <el-autocomplete
                  :key="`account-wechat-select-${wechatSelectVersion}`"
                  v-model="wechatForm.app_id"
                  clearable
                  value-key="app_id"
                  :fetch-suggestions="queryWechatCredentials"
                  placeholder="输入或选择公众号 AppID"
                  @input="handleWechatAppIdInput"
                  @select="selectWechatCredential"
                  @blur="handleWechatAppIdBlur"
                  @clear="clearWechatCredentialSelection"
                >
                  <template #suffix>
                    <el-icon class="credential-dropdown-icon"><ArrowDown /></el-icon>
                  </template>
                  <template #default="{ item: credential }">
                    <div class="credential-option">
                      <span>{{ credential.app_id }}</span>
                      <el-button
                        class="credential-delete"
                        text
                        circle
                        :icon="Close"
                        :loading="loadingAction === `wechat-delete-${credential.account_id}`"
                        aria-label="清除已保存账号记录"
                        title="清除已保存账号记录"
                        @click="deleteWechatCredential(credential, $event)"
                      />
                    </div>
                  </template>
                </el-autocomplete>
              </el-form-item>
              <el-form-item label="AppSecret" prop="app_secret">
                <el-input
                  v-model="wechatForm.app_secret"
                  type="password"
                  show-password
                  autocomplete="new-password"
                  placeholder="请输入 AppSecret"
                >
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
                登录
              </el-button>
            </el-form>
          </el-popover>

          <el-popover v-if="platform.key === 'bilibili'" v-model:visible="bilibiliConfigVisible" placement="bottom-end" :width="420" trigger="click">
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
              <el-form-item label="B 站账号" prop="username">
                <el-input v-model="bilibiliForm.username" autocomplete="username" placeholder="手机号或邮箱">
                  <template #prefix>
                    <el-icon><Key /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item label="B 站密码" prop="password">
                <el-input v-model="bilibiliForm.password" type="password" show-password autocomplete="current-password" placeholder="请输入密码">
                  <template #prefix>
                    <el-icon><Key /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              <el-form-item label="验证码">
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

          <el-tag v-if="platform.disabled" type="info">后续阶段接入</el-tag>

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

.account-view.is-compact .account-table {
  overflow: visible;
}

.account-view.is-compact .account-row {
  grid-template-columns: minmax(160px, 0.8fr) minmax(140px, 0.8fr) minmax(180px, 1fr) minmax(320px, 1.4fr);
  border-bottom: 0;
}

.direct-config-panel {
  padding-top: 4px;
}

.direct-config-panel .account-form {
  max-width: none;
}

.direct-config-panel :deep(.el-form-item) {
  margin-bottom: 14px;
}

.direct-config-actions {
  display: flex;
  justify-content: flex-end;
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

.account-form .el-select,
.account-form .el-autocomplete {
  width: 100%;
}

.form-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: #172033;
  font-size: 14px;
  font-weight: 600;
}

.credential-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.credential-option span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.credential-delete {
  flex: 0 0 auto;
  color: #607086;
}

.credential-dropdown-icon {
  color: #8492a6;
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
