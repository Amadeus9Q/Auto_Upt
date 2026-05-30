export type PlatformKey = "wechat" | "zhihu" | "xiaohongshu" | "bilibili";
export type ContentType = "article" | "video" | "mixed";
export type PublishMode = "simulate" | "draft" | "publish";
export type PublishStatus = "pending" | "running" | "succeeded" | "failed";
export type AccountStatus = "not_configured" | "connected" | "expired" | "error";

export interface ContentPayload {
  title?: string;
  body: string;
  content_type: ContentType;
  tags: string[];
  assets: AssetPayload[];
  content_blocks?: ContentBlockPayload[];
  cover_asset_id?: string | null;
  platforms?: PlatformKey[];
}

export interface AssetPayload {
  id: string;
  name: string;
  type: "image" | "video" | "audio" | "cover" | "body_image";
  size: number;
  mime_type: string;
  usage: string;
  preview_url?: string;
}

export type ContentBlockPayload =
  | { type: "text"; text: string }
  | { type: "asset"; asset_id: string; asset_kind: "image" | "video" | "audio"; role?: "inline" | "cover" };

export interface DraftAssetPayload {
  id?: string;
  name?: string;
  type?: string;
  preview_url?: string;
  url?: string;
  mime_type?: string;
}

export interface DraftBodyBlockPayload {
  type: "text" | "asset";
  text?: string;
  asset_kind?: "image" | "video" | "audio";
  asset?: DraftAssetPayload;
}

export interface DraftRichBlockPayload {
  type: string;
  text?: string;
  level?: number;
  src?: string;
  alt?: string;
  mime_type?: string;
}

export interface DraftPayload {
  platform: PlatformKey;
  display_name: string;
  title: string;
  body: string;
  summary: string;
  tags: string[];
  assets: unknown[];
  body_blocks?: DraftBodyBlockPayload[];
  media_slots?: Record<string, unknown>;
  rich_body?: DraftRichBlockPayload[];
  cover_image?: DraftAssetPayload | null;
  author?: string;
  style_notes: string[];
  metadata: Record<string, unknown>;
}

export interface ValidationIssue {
  level: "info" | "warning" | "error";
  code: string;
  field: string;
  message: string;
}

export interface PreviewResponse {
  preview_id: string;
  content_ir: Record<string, unknown>;
  drafts: Partial<Record<PlatformKey, DraftPayload>>;
  validation_report: Partial<Record<PlatformKey, ValidationIssue[]>>;
  created_at: string | null;
}

export interface PublishTaskResponse {
  task_id: string;
  preview_id: string;
  mode: PublishMode;
  status: PublishStatus;
  platforms: PlatformKey[];
  results: Partial<Record<PlatformKey, PublishResult>>;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PublishResult {
  platform: PlatformKey;
  display_name?: string;
  mode?: PublishMode;
  status: "succeeded" | "failed";
  preview?: DraftPayload;
  preview_url?: string;
  screenshot_path?: string;
  message: string;
}

export interface AccountConnection {
  account_id: string | null;
  platform: PlatformKey;
  display_name: string;
  status: AccountStatus;
  auth_type: string;
  real_publish_supported: boolean;
  required_for_real_publish: boolean;
  capabilities: Record<string, unknown>;
  external_user_id?: string | null;
  token_expires_at?: string | null;
  message: string;
}

export interface AccountListResponse {
  accounts: AccountConnection[];
}

export interface WechatConnectPayload {
  app_id: string;
  app_secret: string;
  display_name?: string;
}

export interface BilibiliCaptchaResponse {
  gt: string;
  challenge: string;
  token: string;
}

export interface BilibiliLoginPayload {
  username: string;
  password: string;
  token: string;
  challenge: string;
  validate: string;
  seccode: string;
  display_name?: string;
}

export interface BilibiliLoginResponse {
  account: AccountConnection;
  message: string;
}

export interface AccountTestResponse {
  account: AccountConnection;
  ok: boolean;
  message: string;
  details: Record<string, unknown>;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    }
  });

  if (!response.ok) {
    const detail = await response.text();
    let message = detail || `Request failed with ${response.status}`;
    try {
      const payload = JSON.parse(detail) as { detail?: string | { msg?: string }[] };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (Array.isArray(payload.detail) && payload.detail[0]?.msg) {
        message = payload.detail[0].msg;
      }
    } catch {
      // Keep the raw response body when it is not JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export function createPreview(payload: ContentPayload): Promise<PreviewResponse> {
  return request<PreviewResponse>("/api/v1/previews", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function createPublishTask(
  previewId: string,
  platforms?: PlatformKey[],
  mode: PublishMode = "simulate",
  accountIds?: Partial<Record<PlatformKey, string>>,
  platformOptions?: Partial<Record<PlatformKey, Record<string, unknown>>>
): Promise<PublishTaskResponse> {
  return request<PublishTaskResponse>("/api/v1/publish-tasks", {
    method: "POST",
    body: JSON.stringify({
      preview_id: previewId,
      mode,
      platforms,
      account_ids: accountIds ?? {},
      platform_options: platformOptions ?? {}
    })
  });
}

export function getAccounts(): Promise<AccountConnection[]> {
  return request<AccountListResponse>("/api/v1/accounts").then((response) => response.accounts);
}

export function connectWechatAccount(payload: WechatConnectPayload): Promise<AccountConnection> {
  return request<AccountConnection>("/api/v1/accounts/wechat/connect", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getBilibiliCaptcha(): Promise<BilibiliCaptchaResponse> {
  return request<BilibiliCaptchaResponse>("/api/v1/accounts/bilibili/login/captcha");
}

export function loginBilibili(payload: BilibiliLoginPayload): Promise<BilibiliLoginResponse> {
  return request<BilibiliLoginResponse>("/api/v1/accounts/bilibili/login/password", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function testAccountConnection(platform: PlatformKey): Promise<AccountTestResponse> {
  return request<AccountTestResponse>(`/api/v1/accounts/${platform}/test`, {
    method: "POST"
  });
}

export async function deleteAccount(accountId: string): Promise<AccountConnection> {
  return request<AccountConnection>(`/api/v1/accounts/connections/${accountId}`, {
    method: "DELETE"
  });
}
