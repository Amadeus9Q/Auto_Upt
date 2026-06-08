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
  content_points?: string[];
  highlights?: string[];
  zhihu_blocks?: ZhihuBlockPayload[];
}

export interface ZhihuBlockPayload {
  type: "conclusion" | "heading-1" | "heading-2" | "text" | "separator" | "quote" | "image";
  text?: string;
  detail?: string;
  src?: string;
  name?: string;
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

export interface PreviewDraftUpdatePayload {
  title?: string;
  body?: string;
  summary?: string;
  tags?: string[];
}

export type AgentStyleGoal = "professional" | "knowledge" | "social" | "video" | "original";
export type AgentRewriteStrength = "light" | "medium" | "strong";
export type AgentLlmMode = "auto" | "enabled" | "disabled";
export type AgentWritingStyle = "default" | "professional" | "concise" | "vivid" | "custom";

export interface AgentAdaptPreviewPayload extends ContentPayload {
  preview_id?: string | null;
  style_goal?: AgentStyleGoal;
  rewrite_strength?: AgentRewriteStrength;
  writing_style?: AgentWritingStyle;
  custom_writing_style?: string | null;
  overwrite_existing_metadata?: boolean;
  update_title?: boolean;
  update_tags?: boolean;
  use_llm?: AgentLlmMode;
  persist_preview?: boolean;
}

export interface AgentToolCall {
  name: string;
  description: string;
  status: "succeeded" | "skipped" | "failed";
  input_summary: string;
  output: Record<string, unknown>;
  started_at: string;
  completed_at: string;
}

export interface AgentGeneratedMetadata {
  title: string;
  tags: string[];
  summary: string;
  source: string;
}

export interface AgentRewrittenContent {
  title: string;
  body: string;
  tags: string[];
  style_goal: AgentStyleGoal;
  rewrite_strength: AgentRewriteStrength;
  source: string;
}

export interface AgentAdaptPreviewResponse {
  run_id: string;
  status: "succeeded" | "skipped" | "failed";
  preview_id: string | null;
  tool_calls: AgentToolCall[];
  metadata: AgentGeneratedMetadata;
  rewritten_content: AgentRewrittenContent;
  content_ir: Record<string, unknown>;
  drafts: Partial<Record<PlatformKey, DraftPayload>>;
  validation_report: Partial<Record<PlatformKey, ValidationIssue[]>>;
  compliance_report: Record<string, ValidationIssue[]>;
  recommendations: string[];
  created_at: string;
  llm_status: "available" | "degraded" | "disabled";
}

export interface PublishTaskResponse {
  task_id: string;
  preview_id: string;
  mode: PublishMode;
  status: PublishStatus;
  platforms: PlatformKey[];
  account_ids: Partial<Record<PlatformKey, string>>;
  asset_ids: Partial<Record<PlatformKey, string[]>>;
  platform_options: Partial<Record<PlatformKey, Record<string, unknown>>>;
  results: Partial<Record<PlatformKey, PublishResult>>;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PublishTaskListResponse {
  tasks: PublishTaskResponse[];
}

export interface PublishResult {
  platform: PlatformKey;
  display_name?: string;
  mode?: PublishMode;
  status: PublishStatus;
  preview?: DraftPayload;
  preview_url?: string;
  screenshot_path?: string;
  publication_id?: string;
  external_id?: string;
  external_url?: string;
  external_status?: string;
  platform_code?: string;
  platform_options?: Record<string, unknown>;
  api_payload?: Record<string, unknown>;
  retryable?: boolean;
  next_action?: string;
  message: string;
}

export interface DraftUpdatePayload {
  title?: string | null;
  body?: string | null;
  tags?: string[] | null;
}

export interface DraftUpdateResponse {
  preview_id: string;
  platform: string;
  draft: DraftPayload;
  validation_report: ValidationIssue[];
}

export interface ImportedMediaPayload {
  index: number;
  name: string;
  kind: "image" | "video" | "audio";
  description?: string | null;
}

export interface ImportChapterPayload {
  level: number;
  title: string;
  content: string;
  start_index: number;
  word_count: number;
  sub_chapters?: ImportChapterPayload[];
}

export interface ImportDocumentResponse {
  title: string;
  subtitle?: string;
  body: string;
  tags: string[];
  content_type: ContentType;
  summary: string;
  media: ImportedMediaPayload[];
  chapters?: ImportChapterPayload[];
  raw_text: string;
}

export function updatePlatformDraft(
  previewId: string,
  platform: PlatformKey,
  payload: DraftUpdatePayload,
): Promise<DraftUpdateResponse> {
  return request<DraftUpdateResponse>(`/api/v1/previews/${encodeURIComponent(previewId)}/drafts/${encodeURIComponent(platform)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function importDocument(file: File): Promise<ImportDocumentResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return request<ImportDocumentResponse>("/api/v1/content/import", {
    method: "POST",
    body: formData,
  });
}

export interface PublishTaskCreatePayload {
  preview_id: string;
  mode?: PublishMode;
  platforms?: PlatformKey[];
  account_ids?: Partial<Record<PlatformKey, string>>;
  asset_ids?: Partial<Record<PlatformKey, string[]>>;
  platform_options?: Partial<Record<PlatformKey, Record<string, unknown>>>;
  inline_drafts?: Partial<Record<PlatformKey, DraftPayload>>;
  inline_content_ir?: Record<string, unknown>;
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
  saved_credentials?: SavedCredentialOption[];
  message: string;
}

export interface SavedCredentialOption {
  account_id: string;
  app_id: string;
  display_name: string;
  status: AccountStatus;
  has_secret: boolean;
  is_active: boolean;
  token_expires_at?: string | null;
}

export interface AccountListResponse {
  accounts: AccountConnection[];
}

export interface WechatConnectPayload {
  app_id: string;
  app_secret?: string | null;
  account_id?: string | null;
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

export interface AccountSecretRevealResponse {
  account_id: string;
  platform: PlatformKey;
  app_id: string;
  app_secret: string;
}

export interface UploadedAssetResponse {
  asset_id: string;
  asset_type: string;
  purpose: string;
  original_filename: string;
  filename: string;
  content_type: string;
  file_size: number;
  sha256: string;
  url: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
}

export interface PublicationResponse {
  publication_id: string;
  task_id: string;
  preview_id: string;
  account_id: string | null;
  platform: PlatformKey;
  mode: PublishMode;
  status: string;
  external_id: string | null;
  external_url: string | null;
  external_status: string | null;
  response_payload: Record<string, unknown>;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PublicationPublishResponse {
  publication: PublicationResponse;
  message: string;
  details: Record<string, unknown>;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers
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

export function updatePreviewDraft(previewId: string, platform: PlatformKey, payload: PreviewDraftUpdatePayload): Promise<PreviewResponse> {
  return request<PreviewResponse>(`/api/v1/previews/${previewId}/drafts/${platform}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function runAgentAdaptPreview(payload: AgentAdaptPreviewPayload): Promise<AgentAdaptPreviewResponse> {
  return request<AgentAdaptPreviewResponse>("/api/v1/agent-runs/adapt-preview", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function createPublishTask(payload: PublishTaskCreatePayload): Promise<PublishTaskResponse> {
  return request<PublishTaskResponse>("/api/v1/publish-tasks", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export interface ListPublishTasksParams {
  mode?: PublishMode;
  status?: PublishStatus;
  platform?: PlatformKey;
  limit?: number;
}

export function listPublishTasks(params: ListPublishTasksParams = {}): Promise<PublishTaskResponse[]> {
  const searchParams = new URLSearchParams();
  if (params.mode) searchParams.set("mode", params.mode);
  if (params.status) searchParams.set("status", params.status);
  if (params.platform) searchParams.set("platform", params.platform);
  if (params.limit) searchParams.set("limit", String(params.limit));
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : "";
  return request<PublishTaskListResponse>(`/api/v1/publish-tasks${suffix}`).then((response) => response.tasks);
}

export function getPublishTask(taskId: string): Promise<PublishTaskResponse> {
  return request<PublishTaskResponse>(`/api/v1/publish-tasks/${taskId}`);
}

export function refreshPublishTask(taskId: string): Promise<PublishTaskResponse> {
  return request<PublishTaskResponse>(`/api/v1/publish-tasks/${taskId}/refresh`, {
    method: "POST"
  });
}

export function publishDraftPublication(publicationId: string): Promise<PublicationPublishResponse> {
  return request<PublicationPublishResponse>(`/api/v1/publications/${publicationId}/publish`, {
    method: "POST"
  });
}

export function uploadAsset(file: File, assetType: "image" | "video" | "file", purpose: string): Promise<UploadedAssetResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("asset_type", assetType);
  formData.append("purpose", purpose);

  return request<UploadedAssetResponse>("/api/v1/assets", {
    method: "POST",
    body: formData
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

export function revealAccountSecret(accountId: string): Promise<AccountSecretRevealResponse> {
  return request<AccountSecretRevealResponse>(`/api/v1/accounts/connections/${accountId}/reveal-secret`, {
    method: "POST"
  });
}
