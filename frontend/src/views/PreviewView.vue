<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import type { PlatformKey, ValidationIssue } from "@/api/client";
import { updatePlatformDraft } from "@/api/client";
import WechatPreview from "@/views/WechatPreview.vue";
import type { RichBlock } from "@/views/WechatPreview.vue";

interface DraftAsset {
  id?: string;
  name?: string;
  type?: string;
  preview_url?: string;
  url?: string;
  mime_type?: string;
}

interface DraftBodyBlock {
  type: "text" | "asset";
  text?: string;
  asset_kind?: "image" | "video" | "audio";
  asset?: DraftAsset;
}

interface ZhihuBlock {
  type: "conclusion" | "heading-1" | "heading-2" | "text" | "separator" | "quote" | "image";
  text?: string;
  detail?: string;
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
  rich_body?: RichBlock[];
  cover_image?: { url?: string; preview_url?: string; name?: string } | null;
  body_blocks?: DraftBodyBlock[];
  media_slots?: Record<string, unknown>;
  author?: string;
  metadata?: { estimated_read_time_minutes?: number; source_word_count?: number };
  content_points?: string[];
  highlights?: string[];
  zhihu_blocks?: ZhihuBlock[];
}

const props = defineProps<{
  drafts: PlatformDraft[];
  loading: boolean;
  errorMessage: string;
  previewId: string;
  createdAt: string;
}>();

const emit = defineEmits<{
  confirmPublish: [];
  "update:drafts": [drafts: PlatformDraft[]];
}>();

/** 本地可编辑的草稿副本，初始从 props 同步 */
const localDrafts = ref<PlatformDraft[]>([...props.drafts]);

watch(
  () => props.drafts,
  (drafts) => {
    localDrafts.value = drafts.map((d) => ({ ...d, tags: [...d.tags], issues: [...d.issues], metrics: [...d.metrics] }));
  },
  { deep: true },
);

const emitDraftUpdate = () => emit("update:drafts", localDrafts.value);

// ---- 平台独立编辑状态 ----
interface EditBuffer {
  title: string;
  body: string;
  tagsText: string; // 逗号分隔的标签输入
}

const editingPlatforms = ref<Set<PlatformKey>>(new Set());
const savingPlatforms = ref<Set<PlatformKey>>(new Set());
const editBuffers = reactive<Partial<Record<PlatformKey, EditBuffer>>>({});

function isEditing(platform: PlatformKey) {
  return editingPlatforms.value.has(platform);
}

function isSaving(platform: PlatformKey) {
  return savingPlatforms.value.has(platform);
}

function enterEdit(platform: PlatformKey) {
  if (!localDrafts.value) return;
  const draft = localDrafts.value.find((d) => d.key === platform);
  if (!draft) return;

  editBuffers[platform] = {
    title: draft.title,
    body: draft.body,
    tagsText: draft.tags.join("、"),
  };
  editingPlatforms.value.add(platform);
}

function cancelEdit(platform: PlatformKey) {
  editingPlatforms.value.delete(platform);
  delete editBuffers[platform];
}

async function saveDraft(platform: PlatformKey) {
  const buffer = editBuffers[platform];
  if (!buffer) return;

  savingPlatforms.value.add(platform);
  try {
    const res = await updatePlatformDraft(props.previewId, platform, {
      title: buffer.title || null,
      body: buffer.body || null,
      tags: buffer.tagsText
        ? buffer.tagsText.split(/[,，、\s]+/).filter(Boolean)
        : [],
    });

    // 更新本地草稿
    const idx = localDrafts.value.findIndex((d) => d.key === platform);
    if (idx >= 0) {
      const draft = res.draft;
      const issues = res.validation_report ?? [];
      const warnings = issues.filter((i) => i.level === "warning" || i.level === "error").length;
      localDrafts.value[idx] = {
        ...localDrafts.value[idx],
        title: draft.title ?? localDrafts.value[idx].title,
        body: draft.body ?? localDrafts.value[idx].body,
        tags: draft.tags ?? localDrafts.value[idx].tags,
        summary: draft.summary ?? localDrafts.value[idx].summary,
        issues,
        status: warnings > 0 ? "warning" : "ready",
        zhihu_blocks: (draft as any).zhihu_blocks ?? localDrafts.value[idx].zhihu_blocks,
        content_points: draft.content_points ?? localDrafts.value[idx].content_points,
        highlights: draft.highlights ?? localDrafts.value[idx].highlights,
        metrics: [
          { label: "标题", value: `${draft.title?.length ?? 0} 字` },
          { label: "正文", value: `${draft.body?.length ?? 0} 字` },
          { label: "校验", value: `${issues.length} 项` },
        ],
      };
    }

    editingPlatforms.value.delete(platform);
    delete editBuffers[platform];
    emitDraftUpdate();
  } catch (err: any) {
    console.error("保存草稿失败:", err);
  } finally {
    savingPlatforms.value.delete(platform);
  }
}

// ---- 现有 computed（基于 localDrafts） ----

const currentPlatform = ref<PlatformKey>("wechat");

const activeDraft = computed(() => localDrafts.value.find((draft) => draft.key === currentPlatform.value) ?? null);

const bilibiliMainVideo = computed(() => (activeDraft.value?.key === "bilibili" ? slotAsset(activeDraft.value, "main_video") : null));
const bilibiliCover = computed(() => (activeDraft.value?.key === "bilibili" ? activeDraft.value.cover_image ?? slotAsset(activeDraft.value, "cover") : null));
const bilibiliHighlights = computed(() => {
  if (activeDraft.value?.content_points?.length) {
    return activeDraft.value.content_points;
  }
  return draftHighlights(activeDraft.value, 5);
});

const zhihuParagraphs = computed(() => textParagraphs(activeDraft.value?.body ?? "").filter((paragraph) => !isAssetMarkerText(paragraph)));
const zhihuImages = computed(() => (activeDraft.value?.key === "zhihu" ? slotAssetList(activeDraft.value, "body_images").slice(0, 3) : []));
const zhihuUnsupportedMedia = computed(() =>
  activeDraft.value?.key === "zhihu" ? [...slotAssetList(activeDraft.value, "body_videos"), ...slotAssetList(activeDraft.value, "body_audios")] : []
);

const xiaohongshuCover = computed(() => {
  if (activeDraft.value?.key !== "xiaohongshu") {
    return null;
  }
  return activeDraft.value.cover_image ?? slotAsset(activeDraft.value, "cover") ?? slotAssetList(activeDraft.value, "body_images")[0] ?? null;
});
const xiaohongshuHighlights = computed(() => {
  if (activeDraft.value?.highlights?.length) {
    return activeDraft.value.highlights;
  }
  return draftHighlights(activeDraft.value, 4);
});
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
  () => localDrafts.value,
  (drafts) => {
    if (drafts.length && !drafts.some((draft) => draft.key === currentPlatform.value)) {
      currentPlatform.value = drafts[0].key;
    }
  },
  { immediate: true }
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

function textParagraphs(text: string) {
  return text
    .split(/\n{1,}/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function isAssetMarkerText(text: string) {
  return /^\{\{asset:(image|video|audio):[^}]+}}$/.test(text) || /^【(图片|视频|音频)[:：].+】$/.test(text);
}

function draftHighlights(draft: PlatformDraft | null, limit: number) {
  if (!draft) {
    return [];
  }

  const blocks = draft.body_blocks
    ?.filter((block) => block.type === "text" && block.text?.trim())
    .map((block) => block.text?.trim() ?? "");
  if (blocks?.length) {
    return blocks.slice(0, limit);
  }

  const paragraphs = textParagraphs(draft.body).filter((item) => !item.startsWith("#"));
  return (paragraphs.length ? paragraphs : [draft.summary]).filter(Boolean).slice(0, limit);
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
            v-for="draft in localDrafts"
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
      v-if="!loading && localDrafts.length === 0 && !errorMessage"
      description="还没有生成预览"
    />

    <template v-if="activeDraft">
      <!-- ===== 编辑工具栏（每个平台独立） ===== -->
      <div class="edit-toolbar">
        <template v-if="isEditing(activeDraft.key)">
          <span class="edit-badge">✎ 编辑 {{ activeDraft.label }}</span>
          <div class="edit-actions">
            <el-button size="small" @click="cancelEdit(activeDraft.key)">取消</el-button>
            <el-button
              size="small"
              type="primary"
              :loading="isSaving(activeDraft.key)"
              @click="saveDraft(activeDraft.key)"
            >
              保存到 {{ activeDraft.label }}
            </el-button>
          </div>
        </template>
        <template v-else>
          <span></span>
          <el-button size="small" text type="primary" @click="enterEdit(activeDraft.key)">
            ✎ 编辑{{ activeDraft.label }}草稿
          </el-button>
        </template>
      </div>

      <!-- ===== 编辑面板 ===== -->
      <div v-if="isEditing(activeDraft.key)" class="edit-panel">
        <el-form label-position="top" size="small">
          <el-form-item label="标题">
            <el-input
              v-model="editBuffers[activeDraft.key]!.title"
              maxlength="200"
              show-word-limit
            />
          </el-form-item>
          <el-form-item label="正文">
            <el-input
              v-model="editBuffers[activeDraft.key]!.body"
              type="textarea"
              :rows="10"
              resize="vertical"
            />
          </el-form-item>
          <el-form-item label="标签（逗号或顿号分隔）">
            <el-input
              v-model="editBuffers[activeDraft.key]!.tagsText"
              placeholder="如：科技、AI、编程"
            />
          </el-form-item>
        </el-form>
      </div>

      <div class="platform-preview-scroll">
        <WechatPreview
          v-if="activeDraft.key === 'wechat'"
          :title="activeDraft.title"
          :summary="activeDraft.summary"
          :body="activeDraft.body"
          :tags="activeDraft.tags"
          :rich-body="activeDraft.rich_body"
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
            <img
              v-else-if="assetSrc(bilibiliCover)"
              :src="assetSrc(bilibiliCover)"
              :alt="bilibiliCover?.name || 'B站封面'"
            />
            <div v-else class="bilibili-player-empty">
              <strong>待选择主视频</strong>
              <span>B站真实发布需要视频素材</span>
            </div>
          </section>

          <section class="bilibili-info">
            <h2>{{ activeDraft.title }}</h2>
            <div class="bilibili-meta">
              <span>{{ activeDraft.title.length }} 字</span>
              <span>{{ activeDraft.body.length }} 字</span>
              <span>{{ activeDraft.tags.length }} 标签</span>
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
                <strong>{{ activeDraft.author || "Auto_Upt 创作助手" }}</strong>
                <span>内容创作、平台适配、发布流程</span>
              </div>
            </div>
          </header>

          <div v-if="activeDraft.tags.length" class="zhihu-topic-row">
            <el-tag v-for="tag in activeDraft.tags" :key="tag" effect="plain">
              {{ tag }}
            </el-tag>
          </div>

          <section class="zhihu-answer-shell">
            <div class="zhihu-answer">
              <!-- 优先用结构化块渲染 -->
              <template v-if="activeDraft.zhihu_blocks?.length">
                <template v-for="(block, bi) in activeDraft.zhihu_blocks" :key="bi">
                  <!-- 结论 -->
                  <p v-if="block.type === 'conclusion'" class="zh-conclusion">
                    <strong>先说结论：</strong>{{ block.text?.replace(/^先说结论：/, "") }}
                  </p>

                  <!-- 一级标题：▎ -->
                  <h3 v-else-if="block.type === 'heading-1'" class="zh-h1">{{ block.text }}</h3>

                  <!-- 二级标题 -->
                  <h4 v-else-if="block.type === 'heading-2'" class="zh-h2">{{ block.text }}</h4>

                  <!-- 正文 -->
                  <p v-else-if="block.type === 'text'" class="zh-text">{{ block.text }}</p>

                  <!-- 分隔线 -->
                  <hr v-else-if="block.type === 'separator'" class="zh-sep" />

                  <!-- 引用块 -->
                  <blockquote v-else-if="block.type === 'quote'" class="zh-quote">
                    <p v-if="block.text">{{ block.text }}</p>
                    <p v-if="block.detail" class="zh-quote-detail">{{ block.detail }}</p>
                  </blockquote>

                  <!-- 图片占位 -->
                  <figure v-else-if="block.type === 'image'" class="zh-image">
                    <img v-if="block.src" :src="block.src" :alt="block.name || '插图'" />
                    <figcaption v-else>[ 图片：{{ block.name || "插图" }} ]</figcaption>
                  </figure>
                </template>
              </template>

              <!-- 兜底：纯文本段落 -->
              <template v-else>
                <p v-for="paragraph in zhihuParagraphs" :key="paragraph">{{ paragraph }}</p>
              </template>
            </div>
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
            <strong>当前阶段仅提示，不参与发布适配</strong>
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
          <div class="phone-status-bar">
            <span>12:00</span>
            <span>小红书</span>
            <span>100%</span>
          </div>
          <div class="xhs-nav">
            <span>‹</span>
            <strong>笔记预览</strong>
            <span>···</span>
          </div>

          <div class="xhs-phone-scroll">
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
                <strong>封面占位</strong>
                <span>建议上传一张竖版或 3:4 图片</span>
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
          </div>
        </section>

        <aside class="xhs-detail-panel">
          <section>
            <span>标题</span>
            <strong>{{ activeDraft.title.length }} 字</strong>
          </section>
          <section>
            <span>正文</span>
            <strong>{{ activeDraft.body.length }} 字</strong>
          </section>
          <section>
            <span>话题</span>
            <strong>{{ activeDraft.tags.length }} 个</strong>
          </section>
          <section v-if="xiaohongshuUnsupportedMedia.length" class="media-pending-card">
            <span>音视频素材</span>
            <strong>当前阶段仅提示，不参与发布适配</strong>
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
          <div v-if="activeDraft.body_blocks?.length" class="block-preview">
            <template v-for="(block, index) in activeDraft.body_blocks" :key="index">
              <pre v-if="block.type === 'text'" class="text-block">{{ block.text }}</pre>
              <figure v-else-if="block.asset_kind === 'image'" class="asset-block">
                <img v-if="assetSrc(block.asset)" :src="assetSrc(block.asset)" :alt="block.asset?.name || '图片素材'" />
                <figcaption>{{ block.asset?.name || "图片素材" }}</figcaption>
              </figure>
              <figure v-else-if="block.asset_kind === 'video'" class="asset-block">
                <video v-if="assetSrc(block.asset)" :src="assetSrc(block.asset)" controls />
                <figcaption>{{ block.asset?.name || "视频素材" }}</figcaption>
              </figure>
              <div v-else-if="block.asset_kind === 'audio'" class="audio-block">
                <span>{{ block.asset?.name || "音频素材" }}</span>
                <audio v-if="assetSrc(block.asset)" :src="assetSrc(block.asset)" controls />
              </div>
            </template>
          </div>
          <div v-else class="body-preview">
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
      </div>
    </template>
  </section>
</template>

<style scoped>
.preview-view {
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
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

/* ---- 编辑工具栏 ---- */
.edit-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  padding: 6px 12px;
  background: #f0f7ff;
  border: 1px solid #d0e3f7;
  border-radius: 6px;
}

.edit-badge {
  font-size: 13px;
  font-weight: 600;
  color: #1f6feb;
}

.edit-actions {
  display: flex;
  gap: 8px;
}

.edit-panel {
  margin-bottom: 14px;
  padding: 12px 14px;
  background: #fafbfc;
  border: 1px solid #e8ecf2;
  border-radius: 8px;
}

.edit-panel :deep(.el-form-item) {
  margin-bottom: 10px;
}

.edit-panel :deep(.el-form-item:last-child) {
  margin-bottom: 0;
}

.platform-preview-scroll {
  max-height: min(72vh, 780px);
  min-height: min(540px, 72vh);
  overflow-y: auto;
  overflow-x: hidden;
  padding: 2px 8px 10px 2px;
  scrollbar-gutter: stable;
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
  display: flex;
  flex-direction: column;
  max-height: min(72vh, 760px);
  overflow: hidden;
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

.zhihu-answer-shell {
  margin-top: 22px;
  min-height: 0;
  overflow: hidden;
}

.zhihu-answer {
  max-height: min(44vh, 430px);
  overflow-y: auto;
  padding-right: 8px;
  scrollbar-gutter: stable;
}

.zhihu-answer p {
  margin: 0 0 14px;
  color: #253247;
  font-size: 15px;
  line-height: 1.85;
  word-break: break-word;
}

/* ---- 知乎结构化块样式 ---- */
.zh-conclusion {
  margin: 0 0 18px !important;
  padding: 12px 16px;
  background: #f0f7ff;
  border-left: 4px solid #1f6feb;
  border-radius: 0 6px 6px 0;
  color: #172033 !important;
  font-size: 15px !important;
  line-height: 1.8 !important;
}

.zh-conclusion strong {
  color: #1f6feb;
}

.zh-h1 {
  margin: 24px 0 10px !important;
  padding-left: 12px;
  border-left: 3px solid #1f6feb;
  color: #172033;
  font-size: 18px;
  font-weight: 650;
  line-height: 1.4;
}

.zh-h1::before {
  content: "▎";
  margin-right: 6px;
  color: #1f6feb;
  font-weight: 400;
}

.zh-h2 {
  margin: 18px 0 8px !important;
  color: #253247;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.5;
}

.zh-text {
  margin: 0 0 14px !important;
  color: #253247;
  font-size: 15px;
  line-height: 1.85;
  word-break: break-word;
}

.zh-sep {
  margin: 16px 0;
  border: none;
  border-top: 1px solid #e8ecf2;
}

.zh-quote {
  margin: 12px 0 16px;
  padding: 10px 16px;
  background: #f7f9fb;
  border-left: 3px solid #c6d2e1;
  border-radius: 0 4px 4px 0;
  color: #4f6279;
  font-size: 14px;
  line-height: 1.75;
}

.zh-quote p {
  margin: 0 0 6px;
  font-size: inherit;
  color: inherit;
}

.zh-quote-detail {
  color: #78909c !important;
  font-size: 13px !important;
}

.zh-image {
  margin: 12px 0;
  padding: 8px 12px;
  background: #f7f9fb;
  border: 1px dashed #c6d2e1;
  border-radius: 6px;
  text-align: center;
}

.zh-image img {
  display: block;
  max-width: 100%;
  max-height: 220px;
  margin: 0 auto;
  object-fit: contain;
}

.zh-image figcaption {
  margin-top: 6px;
  color: #9aa9bb;
  font-size: 13px;
}

.zhihu-inline-images {
  display: grid;
  gap: 12px;
  margin: 16px 0 4px;
}

.zhihu-inline-images img {
  display: block;
  width: min(100%, 520px);
  max-height: 260px;
  object-fit: contain;
  background: #f7f9fb;
  border: 1px solid #e2eaf3;
  border-radius: 8px;
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
  display: flex;
  flex-direction: column;
  width: min(100%, 375px);
  height: min(72vh, 760px);
  justify-self: center;
  overflow: hidden;
  border-radius: 20px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.12);
}

.phone-status-bar {
  display: flex;
  justify-content: space-between;
  flex: 0 0 auto;
  padding: 8px 18px 4px;
  background: #fff5f7;
  color: #1a1a1a;
  font-size: 11px;
  font-weight: 500;
}

.xhs-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 0 0 auto;
  padding: 8px 16px;
  background: #ffffff;
  border-bottom: 1px solid #f0d7df;
  color: #1f1f1f;
}

.xhs-nav span {
  font-size: 20px;
  line-height: 1;
}

.xhs-nav strong {
  font-size: 16px;
}

.xhs-phone-scroll {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.xhs-cover {
  display: grid;
  place-items: center;
  aspect-ratio: 3 / 4;
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
  object-fit: cover;
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

.block-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 360px;
  overflow: auto;
  padding: 12px;
  border: 1px solid #dfe5ee;
  border-radius: 6px;
  background: #f7f9fb;
}

.text-block {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: #253247;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.65;
}

.asset-block {
  margin: 0;
  padding: 10px;
  background: #ffffff;
  border: 1px solid #e2eaf3;
  border-radius: 8px;
}

.asset-block img,
.asset-block video {
  display: block;
  width: 100%;
  max-height: 260px;
  object-fit: contain;
  background: #eef3f8;
  border-radius: 6px;
}

.asset-block figcaption {
  margin-top: 8px;
  color: #607086;
  font-size: 12px;
}

.audio-block {
  display: grid;
  grid-template-columns: minmax(120px, 220px) minmax(240px, 1fr);
  align-items: center;
  gap: 12px;
  padding: 10px;
  background: #ffffff;
  border: 1px solid #e2eaf3;
  border-radius: 8px;
}

.audio-block span {
  overflow: hidden;
  color: #253247;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audio-block audio {
  width: 100%;
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
    width: min(100%, 375px);
  }
}

@media (max-width: 680px) {
  .preview-header {
    justify-content: flex-start;
  }

  .audio-block {
    grid-template-columns: 1fr;
  }
}
</style>
