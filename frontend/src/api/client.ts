export type PlatformKey = "wechat" | "zhihu" | "xiaohongshu" | "bilibili";
export type ContentType = "article" | "video" | "mixed";
export type PublishMode = "simulate" | "draft" | "publish";
export type PublishStatus = "pending" | "running" | "succeeded" | "failed";
export type AccountStatus = "connected" | "disconnected" | "expired" | "error";

export interface ContentPayload {
  title?: string;
  body: string;
  content_type: ContentType;
  tags: string[];
  assets: AssetPayload[];
  platforms?: PlatformKey[];
}

export interface AssetPayload {
  name: string;
  type: "image" | "video" | "audio" | "cover" | "body_image";
  size: number;
  mime_type: string;
  usage: string;
}

export interface DraftPayload {
  platform: PlatformKey;
  display_name: string;
  title: string;
  body: string;
  summary: string;
  tags: string[];
  assets: unknown[];
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
  mode?: "simulate";
  status: "succeeded" | "failed";
  preview?: DraftPayload;
  preview_url?: string;
  screenshot_path?: string;
  message: string;
}

export interface AccountConnection {
  platform: PlatformKey;
  display_name: string;
  status: AccountStatus;
  auth_type: string;
  token_expires_at?: string | null;
  updated_at?: string | null;
}

export interface WechatConnectPayload {
  app_id: string;
  app_secret: string;
  display_name?: string;
}

export interface OAuthStartResponse {
  authorization_url?: string;
  callback_message?: string;
}

export interface AccountTestResponse {
  platform: PlatformKey;
  ok: boolean;
  message: string;
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
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function createPreview(payload: ContentPayload): Promise<PreviewResponse> {
  return request<PreviewResponse>("/api/v1/previews", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function createPublishTask(previewId: string, platforms?: PlatformKey[]): Promise<PublishTaskResponse> {
  return request<PublishTaskResponse>("/api/v1/publish-tasks", {
    method: "POST",
    body: JSON.stringify({
      preview_id: previewId,
      mode: "simulate",
      platforms
    })
  });
}

export function getAccounts(): Promise<AccountConnection[]> {
  return request<AccountConnection[]>("/api/v1/accounts");
}

export function connectWechatAccount(payload: WechatConnectPayload): Promise<AccountConnection> {
  return request<AccountConnection>("/api/v1/accounts/wechat/connect", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function startBilibiliOAuth(): Promise<OAuthStartResponse> {
  return request<OAuthStartResponse>("/api/v1/accounts/bilibili/oauth/start");
}

export function testAccountConnection(platform: PlatformKey): Promise<AccountTestResponse> {
  return request<AccountTestResponse>(`/api/v1/accounts/${platform}/test`, {
    method: "POST"
  });
}

export async function deleteAccount(platform: PlatformKey): Promise<void> {
  await request<Record<string, never>>(`/api/v1/accounts/${platform}`, {
    method: "DELETE"
  });
}
