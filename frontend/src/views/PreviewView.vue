<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { PlatformKey, ValidationIssue } from "@/api/client";
import WechatPreview from "@/views/WechatPreview.vue";

interface DraftAsset {
  id?: string;
  name?: string;
  type?: string;
  preview_url?: string;
  url?: string;
  mime_type?: string;
}

export interface BodySegment {
  type: "text" | "image" | "video" | "audio";
  text?: string;
  src?: string;
  name?: string;
}

export interface PlatformDraft {
  key: PlatformKey;
  label: string;
  title: string;
  summary: string;
  body: string;
  tags: string[];
  status: "ready" | "warning" | "pending";
  issues: ValidationIssue[];
  metrics: Array<{ label: string; value: string }>;
  rich_body?: unknown[];
  cover_image?: { url?: string; preview_url?: string; name?: string } | null;
  body_blocks?: unknown[];
  media_slots?: Record<string, unknown>;
  author?: string;
  metadata?: { estimated_read_time_minutes?: number; source_word_count?: number };
}

const props = defineProps<{
  drafts: PlatformDraft[];
  loading: boolean;
  errorMessage: string;
  previewId: string;
  createdAt: string;
  initialPlatform?: PlatformKey;
}>();
defineEmits<{
  confirmPublish: [];
}>();

const currentPlatform = ref<PlatformKey>(props.initialPlatform ?? "wechat");

const activeDraft = computed(() => props.drafts.find((draft) => draft.key === currentPlatform.value) ?? null);

// ---- body 解析：统一从 body 文本提取段落和媒体 ----

const activeBodySegments = computed(() => parseBodySegments(activeDraft.value));

const bilibiliMainVideo = computed(() => (activeDraft.value?.key === "bilibili" ? slotAsset(activeDraft.value, "main_video") : null));
const bilibiliCover = computed(() => (activeDraft.value?.key === "bilibili" ? activeDraft.value.cover_image ?? slotAsset(activeDraft.value, "cover") : null));
const bilibiliHighlights = computed(() => bodyHighlights(activeDraft.value, 3));

const zhihuTextSegments = computed(() => {
  if (activeDraft.value?.key !== "zhihu") return [];
  return activeBodySegments.value.filter((s) => s.type === "text").slice(0, 8);
});
const zhihuImageSegments = computed(() => {
  if (activeDraft.value?.key !== "zhihu") return [];
  return activeBodySegments.value.filter((s) => s.type === "image");
});
const zhihuUnsupportedMedia = computed(() =>
  activeDraft.value?.key === "zhihu" ? [...slotAssetList(activeDraft.value, "body_videos"), ...slotAssetList(activeDraft.value, "body_audios")] : []
);

const xiaohongshuCover = computed(() => {
  if (activeDraft.value?.key !== "xiaohongshu") {
    return null;
  }
  return activeDraft.value.cover_image ?? slotAsset(activeDraft.value, "cover") ?? slotAssetList(activeDraft.value, "body_images")[0] ?? null;
});
const xiaohongshuHighlights = computed(() => bodyHighlights(activeDraft.value, 4));
const xiaohongshuImages = computed(() => {
  if (activeDraft.value?.key !== "xiaohongshu") {
    return [];
  }

  const images = [xiaohongshuCover.value, ...slotAssetList(activeDraft.value, "body_images")].filter(Boolean) as DraftAsset[];
  const seen = new Set<string>();
  return images.filter((image) => {
    const key = image.id || image.url || image.preview_url || image.name;
    if (!key || seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
});
const xiaohongshuUnsupportedMedia = computed(() =>
  activeDraft.value?.key === "xiaohongshu" ? [...slotAssetList(activeDraft.value, "body_videos"), ...slotAssetList(activeDraft.value, "body_audios")] : []
);

watch(
  () => props.drafts,
  (drafts) => {
    if (drafts.length && !drafts.some((draft) => draft.key === currentPlatform.value)) {
      currentPlatform.value = drafts[0].key;
    }
  },
  { immediate: true }
);

watch(
  () => props.initialPlatform,
  (platform) => {
    if (platform) {
      currentPlatform.value = platform;
    }
  }
);

function selectPlatform(key: string) {
  currentPlatform.value = key as PlatformKey;
}

function issueType(issue: ValidationIssue) {
  if (issue.level === "error") return "danger";
  if (issue.level === "warning") return "warning";
  return "info";
}

function assetSrc(asset?: DraftAsset | null) {
  return asset?.url || asset?.preview_url || "";
}

function slotAsset(draft: PlatformDraft, slot: string): DraftAsset | null {
  const value = draft.media_slots?.[slot];
  if (!value || Array.isArray(value) || typeof value !== "object") {
    return null;
  }
  return value as DraftAsset;
}

function slotAssetList(draft: PlatformDraft, slot: string): DraftAsset[] {
  const value = draft.media_slots?.[slot];
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is DraftAsset => Boolean(item) && typeof item === "object");
}

// ---- body 解析工具 ----

const ASSET_MARKER_RE = /^【(图片|视频|音频)[：:]\s*([^】]+)】$/;

function parseBodySegments(draft: PlatformDraft | null): BodySegment[] {
  if (!draft) return [];

  const allAssets = collectDraftAssets(draft);
  const lines = draft.body.split("\n");
  const segments: BodySegment[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;

    const match = trimmed.match(ASSET_MARKER_RE);
    if (match) {
      const kind = match[1] === "图片" ? "image" : match[1] === "视频" ? "video" : "audio";
      const name = match[2].trim();
      const found = findAssetByName(allAssets, name, kind);
      segments.push({ type: kind, src: found?.url || found?.preview_url || "", name });
    } else {
      segments.push({ type: "text", text: trimmed });
    }
  }

  return segments;
}

function collectDraftAssets(draft: PlatformDraft): DraftAsset[] {
  const fromSlots: DraftAsset[] = Object.values(draft.media_slots ?? {})
    .flat()
    .filter((item): item is DraftAsset => Boolean(item) && typeof item === "object");
  const fromAssets = (draft as unknown as Record<string, unknown>).assets as DraftAsset[] | undefined;
  return [...fromSlots, ...(fromAssets ?? [])];
}

function findAssetByName(assets: DraftAsset[], name: string, kind: string): DraftAsset | undefined {
  const typeMap: Record<string, string[]> = {
    image: ["image", "cover"],
    video: ["video"],
    audio: ["audio"]
  };
  const allowedTypes = typeMap[kind] ?? [];
  return assets.find(
    (a) =>
      (a.name && a.name === name) ||
      (allowedTypes.includes(a.type ?? "") && name.includes(a.name ?? ""))
  );
}

/** 从 body 中提取纯文本亮点（非媒体标记、非标题行） */
function bodyHighlights(draft: PlatformDraft | null, limit: number): string[] {
  if (!draft) return [];
  const segments = parseBodySegments(draft);
  const texts = segments
    .filter((s) => s.type === "text" && s.text && !s.text.startsWith("#"))
    .map((s) => s.text!);
  return (texts.length ? texts : [draft.summary]).filter(Boolean).slice(0, limit);
}
</script>

<template>
  <section class="preview-view" v-loading="loading">
    <header class="preview-header">
      <div class="platform-switcher">
        <el-radio-group
          v-model="currentPlatform"
          size="default"
          @change="selectPlatform"
        >
          <el-radio-button
            v-for="draft in drafts"
            :key="draft.key"
            :value="draft.key"
          >
            {{ draft.label }}
            <el-tag
              v-if="draft.status === 'warning'"
              size="small"
              type="warning"
              effect="plain"
              class="switcher-badge"
            >
              {{ draft.issues.length }}
            </el-tag>
          </el-radio-button>
        </el-radio-group>
      </div>
    </header>

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      :closable="false"
      class="preview-alert"
    />

    <el-empty
      v-if="!loading && drafts.length === 0 && !errorMessage"
      description="暂未生成预览"
    />

    <template v-if="activeDraft">
      <WechatPreview
        v-if="activeDraft.key === 'wechat'"
        :title="activeDraft.title"
        :summary="activeDraft.summary"
        :body="activeDraft.body"
        :tags="activeDraft.tags"
        :body-segments="activeBodySegments"
        :cover-image="activeDraft.cover_image"
        :author="activeDraft.author"
        :metadata="activeDraft.metadata"
      />

      <div v-else-if="activeDraft.key === 'bilibili'" class="bilibili-preview">
        <div class="bilibili-main">
          <section class="bilibili-player">
            <video
              v-if="assetSrc(bilibiliMainVideo)"
              :src="assetSrc(bilibiliMainVideo)"
              :poster="assetSrc(bilibiliCover)"
              controls
            />
            <div v-else class="bilibili-player-empty">
              <strong>待选择主视频</strong>
              <span>{{ bilibiliCover ? "已选封面，B 站发布仍需上传视频" : "B 站发布需要视频素材" }}</span>
            </div>
          </section>

          <section class="bilibili-info">
            <h2>{{ activeDraft.title }}</h2>
            <div class="bilibili-meta">
              <span>{{ activeDraft.title.length }}/80 字</span>
              <span>{{ activeDraft.body.length }}/2000 字</span>
              <span>{{ activeDraft.tags.length }}/10 标签</span>
            </div>
            <div v-if="activeDraft.tags.length" class="bilibili-tags">
              <el-tag v-for="tag in activeDraft.tags" :key="tag" effect="plain">
                {{ tag }}
              </el-tag>
            </div>
          </section>
        </div>

        <aside class="bilibili-side">
          <section class="bilibili-upload-card">
            <span>主视频</span>
            <strong>{{ bilibiliMainVideo?.name || "未选择" }}</strong>
          </section>
          <section class="bilibili-upload-card">
            <span>封面</span>
            <strong>{{ bilibiliCover?.name || "未选择" }}</strong>
          </section>
          <section class="bilibili-description">
            <span>视频简介</span>
            <pre>{{ activeDraft.body }}</pre>
          </section>
        </aside>

        <section v-if="bilibiliHighlights.length" class="bilibili-highlights">
          <strong>内容要点</strong>
          <ol>
            <li v-for="item in bilibiliHighlights" :key="item">{{ item }}</li>
          </ol>
        </section>

        <el-collapse v-if="activeDraft.issues.length" class="issues-collapse">
          <el-collapse-item :title="`校验报告（${activeDraft.issues.length} 项）`" name="issues">
            <div class="issue-list">
              <div
                v-for="issue in activeDraft.issues"
                :key="`${issue.code}-${issue.field}`"
                class="issue-item"
              >
                <el-tag :type="issueType(issue)" size="small" effect="plain">{{ issue.level }}</el-tag>
                <span class="issue-field">{{ issue.field }}</span>
                <span class="issue-msg">{{ issue.message }}</span>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <div v-else-if="activeDraft.key === 'zhihu'" class="zhihu-preview">
        <article class="zhihu-article">
          <header class="zhihu-title-area">
            <h2>{{ activeDraft.title }}</h2>
            <div class="zhihu-author-row">
              <span class="zhihu-avatar">知</span>
              <div>
                <strong>{{ activeDraft.author || "Auto_Upt" }}</strong>
                <span>内容创作 · 平台适配 · 发布流程</span>
              </div>
            </div>
          </header>

          <div v-if="activeDraft.tags.length" class="zhihu-topic-row">
            <el-tag v-for="tag in activeDraft.tags" :key="tag" effect="plain">
              {{ tag }}
            </el-tag>
          </div>

          <section class="zhihu-answer">
            <template v-for="(segment, idx) in zhihuTextSegments" :key="'t-' + idx">
              <p>{{ segment.text }}</p>
            </template>
            <template v-for="(segment, idx) in zhihuImageSegments" :key="'i-' + idx">
              <figure class="zhihu-inline-figure">
                <img v-if="segment.src" :src="segment.src" :alt="segment.name || '知乎图片'" />
                <figcaption v-if="segment.name">{{ segment.name }}</figcaption>
              </figure>
            </template>
          </section>

          <footer class="zhihu-action-row">
            <span>赞同 0</span>
            <span>喜欢</span>
            <span>收藏</span>
            <span>评论</span>
          </footer>
        </article>

        <aside class="platform-side-panel">
          <section>
            <span>标题</span>
            <strong>{{ activeDraft.title.length }}/100 字</strong>
          </section>
          <section>
            <span>标签</span>
            <strong>{{ activeDraft.tags.length }}/5 个</strong>
          </section>
          <section>
            <span>建议形态</span>
            <strong>回答 / 专栏草稿</strong>
          </section>
          <section v-if="zhihuUnsupportedMedia.length" class="media-pending-card">
            <span>音视频素材</span>
            <strong>当前阶段仅供展示，暂不参与发布</strong>
          </section>
        </aside>

        <el-collapse v-if="activeDraft.issues.length" class="issues-collapse">
          <el-collapse-item :title="`校验报告（${activeDraft.issues.length} 项）`" name="issues">
            <div class="issue-list">
              <div
                v-for="issue in activeDraft.issues"
                :key="`${issue.code}-${issue.field}`"
                class="issue-item"
              >
                <el-tag :type="issueType(issue)" size="small" effect="plain">{{ issue.level }}</el-tag>
                <span class="issue-field">{{ issue.field }}</span>
                <span class="issue-msg">{{ issue.message }}</span>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <div v-else-if="activeDraft.key === 'xiaohongshu'" class="xhs-preview">
        <section class="xhs-phone">
          <div class="xhs-cover">
            <el-carousel
              v-if="xiaohongshuImages.length"
              height="100%"
              arrow="always"
              indicator-position="outside"
              class="xhs-carousel"
            >
              <el-carousel-item v-for="image in xiaohongshuImages" :key="image.id || image.name || assetSrc(image)">
                <img :src="assetSrc(image)" :alt="image.name || '小红书图片'" />
              </el-carousel-item>
            </el-carousel>
            <div v-else class="xhs-cover-empty">
              <strong>封面预览</strong>
              <span>建议使用竖版或 3:4 尺寸图片</span>
            </div>
          </div>

          <div class="xhs-note-body">
            <h2>{{ activeDraft.title }}</h2>
            <p>{{ activeDraft.summary }}</p>
            <ul v-if="xiaohongshuHighlights.length">
              <li v-for="item in xiaohongshuHighlights" :key="item">{{ item }}</li>
            </ul>
            <div v-if="activeDraft.tags.length" class="xhs-tags">
              <span v-for="tag in activeDraft.tags" :key="tag">#{{ tag }}</span>
            </div>
          </div>

          <footer class="xhs-action-row">
            <span>♡ 0</span>
            <span>☆ 0</span>
            <span>评论 0</span>
          </footer>
        </section>

        <aside class="xhs-detail-panel">
          <section>
            <span>标题</span>
            <strong>{{ activeDraft.title.length }}/20 字</strong>
          </section>
          <section>
            <span>正文</span>
            <strong>{{ activeDraft.body.length }}/1000 字</strong>
          </section>
          <section>
            <span>话题</span>
            <strong>{{ activeDraft.tags.length }}/10 个</strong>
          </section>
          <section v-if="xiaohongshuUnsupportedMedia.length" class="media-pending-card">
            <span>音视频素材</span>
            <strong>当前阶段仅供展示，暂不参与发布</strong>
          </section>
          <section class="xhs-body-preview">
            <span>笔记正文</span>
            <pre>{{ activeDraft.body }}</pre>
          </section>
        </aside>

        <el-collapse v-if="activeDraft.issues.length" class="issues-collapse">
          <el-collapse-item :title="`校验报告（${activeDraft.issues.length} 项）`" name="issues">
            <div class="issue-list">
              <div
                v-for="issue in activeDraft.issues"
                :key="`${issue.code}-${issue.field}`"
                class="issue-item"
              >
                <el-tag :type="issueType(issue)" size="small" effect="plain">{{ issue.level }}</el-tag>
                <span class="issue-field">{{ issue.field }}</span>
                <span class="issue-msg">{{ issue.message }}</span>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <el-form v-else label-position="top" class="preview-form">
        <el-form-item label="标题">
          <el-input :model-value="activeDraft.title" readonly class="readonly-field">
            <template #suffix>
              <span class="char-count">{{ activeDraft.title.length }} 字</span>
            </template>
          </el-input>
        </el-form-item>

        <el-form-item label="摘要">
          <el-input
            :model-value="activeDraft.summary"
            type="textarea"
            :rows="3"
            readonly
            resize="none"
            class="readonly-field"
          />
        </el-form-item>

        <el-form-item label="正文">
          <div class="body-preview">
            <pre>{{ activeDraft.body }}</pre>
          </div>
        </el-form-item>

        <el-form-item v-if="activeDraft.tags.length" label="标签">
          <div class="tag-row">
            <el-tag v-for="tag in activeDraft.tags" :key="tag" effect="plain" round>
              {{ tag }}
            </el-tag>
          </div>
        </el-form-item>

        <div class="metric-row">
          <span v-for="metric in activeDraft.metrics" :key="metric.label">
            {{ metric.label }}：<strong>{{ metric.value }}</strong>
          </span>
        </div>
      </el-form>
    </template>
  </section>
</template>

<style scoped>
.preview-view {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 16px;
}

.platform-switcher {
  flex-shrink: 0;
}

.platform-switcher :deep(.el-radio-button__inner) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.switcher-badge {
  margin-left: 2px;
  font-size: 11px;
  padding: 0 4px;
  height: 18px;
  line-height: 18px;
}

.preview-alert {
  margin-bottom: 18px;
}

.preview-form {
  flex: 1;
}

.readonly-field :deep(.el-input__inner),
.readonly-field :deep(.el-textarea__inner) {
  background: #f7f9fb;
  color: #253247;
  cursor: default;
}

.char-count {
  color: #9aa9bb;
  font-size: 12px;
  user-select: none;
}

.bilibili-preview,
.zhihu-preview,
.xhs-preview {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 34%);
  gap: 18px;
}

.bilibili-main,
.bilibili-side,
.bilibili-highlights,
.zhihu-article,
.platform-side-panel,
.xhs-phone,
.xhs-detail-panel {
  min-width: 0;
}

.bilibili-player {
  display: grid;
  place-items: center;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background: #0f172a;
  border-radius: 8px;
}

.bilibili-player video,
.bilibili-player img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.bilibili-player img {
  object-fit: cover;
}

.bilibili-player-empty {
  display: grid;
  place-items: center;
  gap: 6px;
  color: #cbd5e1;
  text-align: center;
}

.bilibili-player-empty strong {
  color: #ffffff;
  font-size: 18px;
}

.bilibili-player-empty span {
  font-size: 13px;
}

.bilibili-info {
  padding: 16px 0 0;
}

.bilibili-info h2,
.zhihu-title-area h2,
.xhs-note-body h2 {
  margin: 0;
  color: #172033;
  line-height: 1.35;
  word-break: break-word;
}

.bilibili-info h2 {
  font-size: 21px;
}

.bilibili-meta,
.bilibili-tags,
.zhihu-topic-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.bilibili-meta {
  margin-top: 10px;
  color: #607086;
  font-size: 13px;
}

.bilibili-tags {
  margin-top: 14px;
}

.bilibili-side {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.bilibili-upload-card,
.bilibili-description,
.bilibili-highlights,
.zhihu-article,
.platform-side-panel section,
.xhs-phone,
.xhs-detail-panel section {
  border: 1px solid #dfe5ee;
  border-radius: 8px;
  background: #ffffff;
}

.bilibili-upload-card {
  display: grid;
  gap: 5px;
  padding: 12px 14px;
}

.bilibili-upload-card span,
.bilibili-description span,
.bilibili-highlights strong,
.platform-side-panel span,
.xhs-detail-panel span {
  color: #607086;
  font-size: 13px;
}

.bilibili-upload-card strong,
.platform-side-panel strong,
.xhs-detail-panel strong {
  overflow: hidden;
  color: #253247;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bilibili-description {
  min-height: 0;
  padding: 12px 14px;
}

.bilibili-description pre,
.xhs-body-preview pre {
  max-height: 260px;
  overflow: auto;
  margin: 8px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: #253247;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.65;
}

.bilibili-highlights {
  grid-column: 1 / -1;
  padding: 14px 16px;
}

.bilibili-highlights ol {
  margin: 10px 0 0;
  padding-left: 20px;
  color: #253247;
  line-height: 1.65;
}

.zhihu-article {
  max-width: 780px;
  padding: 24px;
}

.zhihu-title-area h2 {
  font-size: 24px;
}

.zhihu-author-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
}

.zhihu-avatar {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  color: #ffffff;
  background: #1f6feb;
  border-radius: 50%;
  font-weight: 700;
}

.zhihu-author-row strong,
.zhihu-author-row span {
  display: block;
}

.zhihu-author-row strong {
  color: #253247;
  font-size: 14px;
}

.zhihu-author-row span {
  margin-top: 2px;
  color: #607086;
  font-size: 12px;
}

.zhihu-topic-row {
  margin-top: 18px;
}

.zhihu-answer {
  margin-top: 22px;
}

.zhihu-answer p {
  margin: 0 0 14px;
  color: #253247;
  font-size: 15px;
  line-height: 1.85;
  word-break: break-word;
}

.zhihu-inline-figure {
  margin: 16px 0 4px;
}

.zhihu-inline-figure img {
  display: block;
  width: min(100%, 520px);
  max-height: 260px;
  object-fit: contain;
  background: #f7f9fb;
  border: 1px solid #e2eaf3;
  border-radius: 8px;
}

.zhihu-inline-figure figcaption {
  margin-top: 6px;
  color: #607086;
  font-size: 12px;
}

.zhihu-action-row,
.xhs-action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 20px;
  color: #607086;
  font-size: 13px;
}

.platform-side-panel,
.xhs-detail-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.platform-side-panel section,
.xhs-detail-panel section {
  display: grid;
  gap: 5px;
  padding: 12px 14px;
}

.platform-side-panel .media-pending-card,
.xhs-detail-panel .media-pending-card {
  background: #fff8ed;
  border-color: #f3d19e;
}

.media-pending-card strong {
  color: #9a5b13;
  white-space: normal;
}

.xhs-phone {
  width: min(100%, 320px);
  justify-self: center;
  overflow: hidden;
}

.xhs-cover {
  display: grid;
  place-items: center;
  aspect-ratio: 4 / 5;
  overflow: hidden;
  background: #f2f6fa;
}

.xhs-carousel,
.xhs-carousel :deep(.el-carousel__container) {
  width: 100%;
  height: 100%;
}

.xhs-carousel :deep(.el-carousel__indicators--outside) {
  transform: translateY(-4px);
}

.xhs-cover img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #f2f6fa;
}

.xhs-cover-empty {
  display: grid;
  place-items: center;
  gap: 6px;
  color: #607086;
  text-align: center;
}

.xhs-cover-empty strong {
  color: #253247;
  font-size: 18px;
}

.xhs-cover-empty span {
  font-size: 13px;
}

.xhs-note-body {
  padding: 16px;
}

.xhs-note-body h2 {
  font-size: 19px;
}

.xhs-note-body p,
.xhs-note-body li {
  color: #253247;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}

.xhs-note-body p {
  margin: 10px 0 0;
}

.xhs-note-body ul {
  display: grid;
  gap: 8px;
  margin: 12px 0 0;
  padding-left: 18px;
}

.xhs-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 14px;
}

.xhs-tags span {
  color: #c04462;
  font-size: 13px;
}

.xhs-action-row {
  margin: 0;
  padding: 12px 16px 14px;
  border-top: 1px solid #edf1f5;
}

.body-preview {
  max-height: 260px;
  overflow: auto;
  border: 1px solid #dfe5ee;
  border-radius: 6px;
  background: #f7f9fb;
}

.body-preview pre {
  margin: 0;
  padding: 14px 16px;
  white-space: pre-wrap;
  word-break: break-word;
  color: #253247;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.65;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.metric-row {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  margin-bottom: 18px;
  padding: 10px 14px;
  background: #f0f3f7;
  border-radius: 6px;
  color: #607086;
  font-size: 13px;
}

.metric-row strong {
  color: #172033;
}

.issues-collapse {
  grid-column: 1 / -1;
  margin-top: 4px;
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.issue-item {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-size: 13px;
}

.issue-field {
  color: #607086;
  min-width: 60px;
}

.issue-msg {
  color: #253247;
}

@media (max-width: 880px) {
  .bilibili-preview,
  .zhihu-preview,
  .xhs-preview {
    grid-template-columns: 1fr;
  }

  .xhs-phone {
    justify-self: stretch;
  }
}

@media (max-width: 680px) {
  .preview-header {
    justify-content: flex-start;
  }
}
</style>
