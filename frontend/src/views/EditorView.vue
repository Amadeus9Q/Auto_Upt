<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import type { UploadFile, UploadProps } from "element-plus";
import { Connection, Delete, EditPen, MagicStick, Plus, Promotion } from "@element-plus/icons-vue";

import type { DraftPayload, PlatformKey } from "@/api/client";

type DraftAssetEntry = { type?: string; name?: string; preview_url?: string; url?: string };

export type MediaKind = "image" | "video" | "audio";

export interface LocalAsset {
  id: string;
  name: string;
  size: number;
  mimeType: string;
  previewUrl: string;
  kind: MediaKind;
  file: File;
  backendAssetId?: string;
  backendUrl?: string;
  uploadPurpose?: string;
}

export interface EditorAssets {
  images: LocalAsset[];
  videos: LocalAsset[];
  audios: LocalAsset[];
  coverImage: LocalAsset | null;
  coverImageId: string | null;
}

type MediaTab = "images" | "videos" | "audios";

interface DragState {
  tab: MediaTab;
  fromIndex: number;
  overIndex: number;
  position: "before" | "after";
}

const props = defineProps<{
  wordCount: number;
  previewLoading: boolean;
  agentLoading: boolean;
  hasPreview: boolean;
  platformDrafts: Partial<Record<PlatformKey, DraftPayload>>;
}>();

const emit = defineEmits<{
  generatePreview: [];
  openPreview: [platform?: PlatformKey];
  confirmPublish: [];
  optimizeAllWithAgent: [];
  optimizeWithAgent: [platform: PlatformKey];
  updatePlatformDraft: [platform: PlatformKey, patch: Partial<Pick<DraftPayload, "title" | "body" | "tags">>];
}>();

const platformOptions: Array<{ label: string; value: PlatformKey }> = [
  { label: "公众号", value: "wechat" },
  { label: "B站", value: "bilibili" },
  { label: "知乎", value: "zhihu" },
  { label: "小红书", value: "xiaohongshu" }
];

const mediaTabs: Array<{ key: MediaTab; label: string; accept: string; addText: string }> = [
  { key: "images", label: "图片", accept: "image/*", addText: "添加图片" },
  { key: "videos", label: "视频", accept: "video/*", addText: "添加视频" },
  { key: "audios", label: "音频", accept: "audio/*", addText: "添加音频" }
];

const title = defineModel<string>("title", { required: true });
const content = defineModel<string>("content", { required: true });
const tags = defineModel<string>("tags", { required: true });
const platforms = defineModel<PlatformKey[]>("platforms", { required: true });
const assets = defineModel<EditorAssets>("assets", { required: true });

const dragState = ref<DragState | null>(null);
const isContentDragOver = ref(false);
const contentDropIndex = ref<number | null>(null);
const isPlatformDragOver = ref(false);
const platformDropIndex = ref<number | null>(null);
const activePreviewPlatform = ref<PlatformKey>("wechat");

const assetCount = computed(() => assets.value.images.length + assets.value.videos.length + assets.value.audios.length);
const activePreviewDraft = computed(() => props.platformDrafts[activePreviewPlatform.value] ?? null);
const activePreviewTitle = computed({
  get: () => activePreviewDraft.value?.title ?? "",
  set: (value: string) => emit("updatePlatformDraft", activePreviewPlatform.value, { title: value })
});
const activePreviewText = computed({
  get: () => activePreviewDraft.value?.body ?? "",
  set: (value: string) => emit("updatePlatformDraft", activePreviewPlatform.value, { body: value })
});
const activePreviewTags = computed({
  get: () => activePreviewDraft.value?.tags?.join(", ") ?? "",
  set: (value: string) => emit("updatePlatformDraft", activePreviewPlatform.value, { tags: parseTagText(value) })
});

function kindFromTab(tab: MediaTab): MediaKind {
  return tab === "images" ? "image" : tab === "videos" ? "video" : "audio";
}

function parseTagText(value: string): string[] {
  return value
    .split(/[,，\s]+/)
    .map((tag) => tag.trim())
    .filter(Boolean);
}

function toLocalAsset(file: UploadFile, tab: MediaTab): LocalAsset | null {
  if (!file.raw) {
    return null;
  }

  return {
    id: `${tab}-${file.uid}`,
    name: file.name,
    size: file.size ?? file.raw.size,
    mimeType: file.raw.type || "application/octet-stream",
    previewUrl: URL.createObjectURL(file.raw),
    kind: kindFromTab(tab),
    file: file.raw
  };
}

const onCoverChange: UploadProps["onChange"] = (file) => {
  assets.value.coverImage = toLocalAsset(file, "images");
  assets.value.coverImageId = null;
};

function createChangeHandler(tab: MediaTab): UploadProps["onChange"] {
  return (file) => {
    const asset = toLocalAsset(file, tab);
    if (!asset || assets.value[tab].some((item) => item.id === asset.id)) {
      return;
    }
    assets.value[tab].push(asset);
  };
}

function removeAsset(tab: MediaTab, index: number) {
  const [removed] = assets.value[tab].splice(index, 1);
  if (tab === "images" && removed?.id === assets.value.coverImageId) {
    assets.value.coverImageId = null;
  }
}

function clearCoverImage() {
  assets.value.coverImage = null;
}

function assetMarker(asset: LocalAsset) {
  const kindLabel: Record<MediaKind, string> = {
    image: "图片",
    video: "视频",
    audio: "音频"
  };
  return `【${kindLabel[asset.kind]}：${asset.name}】`;
}

function insertTextAtCursor(text: string, textarea?: HTMLTextAreaElement | null, target?: { value: string } | null) {
  const ref = target ?? content;
  const marker = `\n\n${text}\n\n`;
  if (!textarea) {
    const prefix = ref.value.trimEnd();
    ref.value = `${prefix}${prefix ? "\n\n" : ""}${text}\n\n`;
    return;
  }

  const start = textarea.selectionStart ?? ref.value.length;
  const end = textarea.selectionEnd ?? start;
  const before = ref.value.slice(0, start).replace(/\s*$/, "");
  const after = ref.value.slice(end).replace(/^\s*/, "");
  const inserted = `${before}${before ? marker : `${text}\n\n`}${after}`;
  const nextCursor = before.length + (before ? marker.length : text.length + 2);
  ref.value = inserted;
  nextTick(() => {
    textarea.focus();
    textarea.setSelectionRange(nextCursor, nextCursor);
  });
}

function insertAssetReference(asset: LocalAsset, textarea?: HTMLTextAreaElement | null, target?: { value: string } | null) {
  insertTextAtCursor(assetMarker(asset), textarea, target);
}

function textareaFromDropEvent(event: DragEvent): HTMLTextAreaElement | null {
  const current = event.currentTarget as HTMLElement | null;
  return current?.querySelector("textarea") ?? null;
}

function measureTextareaCaret(textarea: HTMLTextAreaElement, index: number, mirror: HTMLDivElement, marker: HTMLSpanElement) {
  mirror.textContent = "";
  mirror.append(document.createTextNode(textarea.value.slice(0, index)));
  mirror.append(marker);
  return {
    left: marker.offsetLeft,
    top: marker.offsetTop
  };
}

function buildTextareaMirror(textarea: HTMLTextAreaElement) {
  const style = window.getComputedStyle(textarea);
  const mirror = document.createElement("div");
  const marker = document.createElement("span");
  const copiedProperties = [
    "borderBottomWidth",
    "borderLeftWidth",
    "borderRightWidth",
    "borderTopWidth",
    "boxSizing",
    "fontFamily",
    "fontSize",
    "fontWeight",
    "letterSpacing",
    "lineHeight",
    "paddingBottom",
    "paddingLeft",
    "paddingRight",
    "paddingTop",
    "textAlign",
    "textTransform",
    "wordSpacing"
  ] as const;

  for (const property of copiedProperties) {
    mirror.style[property] = style[property];
  }

  mirror.style.position = "absolute";
  mirror.style.visibility = "hidden";
  mirror.style.whiteSpace = "pre-wrap";
  mirror.style.overflowWrap = "break-word";
  mirror.style.top = "0";
  mirror.style.left = "-9999px";
  mirror.style.width = `${textarea.clientWidth}px`;
  marker.textContent = "\u200b";
  document.body.append(mirror);

  return { mirror, marker };
}

function caretIndexFromPoint(textarea: HTMLTextAreaElement, event: DragEvent) {
  const rect = textarea.getBoundingClientRect();
  const targetX = event.clientX - rect.left + textarea.scrollLeft;
  const targetY = event.clientY - rect.top + textarea.scrollTop;
  const { mirror, marker } = buildTextareaMirror(textarea);
  const valueLength = textarea.value.length;

  try {
    let low = 0;
    let high = valueLength;
    let lineCandidate = 0;

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      const position = measureTextareaCaret(textarea, mid, mirror, marker);
      if (position.top <= targetY) {
        lineCandidate = mid;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }

    const lineTop = measureTextareaCaret(textarea, lineCandidate, mirror, marker).top;
    let lineStart = lineCandidate;
    while (lineStart > 0 && measureTextareaCaret(textarea, lineStart - 1, mirror, marker).top === lineTop) {
      lineStart -= 1;
    }

    let lineEnd = lineCandidate;
    while (lineEnd < valueLength && measureTextareaCaret(textarea, lineEnd + 1, mirror, marker).top === lineTop) {
      lineEnd += 1;
    }

    let bestIndex = lineStart;
    let bestDistance = Number.POSITIVE_INFINITY;
    for (let index = lineStart; index <= lineEnd; index += 1) {
      const position = measureTextareaCaret(textarea, index, mirror, marker);
      const distance = Math.abs(position.left - targetX);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestIndex = index;
      }
    }

    return bestIndex;
  } finally {
    mirror.remove();
  }
}

function previewContentDropPosition(event: DragEvent) {
  const textarea = textareaFromDropEvent(event);
  if (!textarea) {
    contentDropIndex.value = null;
    return null;
  }

  const index = caretIndexFromPoint(textarea, event);
  contentDropIndex.value = index;
  textarea.focus({ preventScroll: true });
  textarea.setSelectionRange(index, index);
  return textarea;
}

function findDraggedAsset(event: DragEvent): LocalAsset | null {
  const payload = event.dataTransfer?.getData("application/x-auto-upt-asset");
  if (payload) {
    try {
      const parsed = JSON.parse(payload) as { tab?: MediaTab; index?: number };
      if (parsed.tab && typeof parsed.index === "number") {
        return assets.value[parsed.tab]?.[parsed.index] ?? null;
      }
    } catch {
      return null;
    }
  }

  if (!dragState.value) {
    return null;
  }
  return assets.value[dragState.value.tab]?.[dragState.value.fromIndex] ?? null;
}

function onContentDragOver(event: DragEvent) {
  if (!findDraggedAsset(event)) {
    return;
  }
  isContentDragOver.value = true;
  previewContentDropPosition(event);
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = "copy";
  }
}

function onContentDrop(event: DragEvent) {
  const asset = findDraggedAsset(event);
  isContentDragOver.value = false;
  if (!asset) {
    return;
  }

  const textarea = previewContentDropPosition(event);
  if (textarea && contentDropIndex.value !== null) {
    textarea.setSelectionRange(contentDropIndex.value, contentDropIndex.value);
  }
  insertAssetReference(asset, textarea);
  contentDropIndex.value = null;
  dragState.value = null;
}

function onContentDragLeave(event: DragEvent) {
  const current = event.currentTarget as HTMLElement;
  const related = event.relatedTarget as Node | null;
  if (!related || !current.contains(related)) {
    isContentDragOver.value = false;
    contentDropIndex.value = null;
  }
}

function previewPlatformDropPosition(event: DragEvent) {
  const textarea = textareaFromDropEvent(event);
  if (!textarea) {
    platformDropIndex.value = null;
    return null;
  }
  const index = caretIndexFromPoint(textarea, event);
  platformDropIndex.value = index;
  textarea.focus({ preventScroll: true });
  textarea.setSelectionRange(index, index);
  return textarea;
}

function onPlatformDragOver(event: DragEvent) {
  if (!findDraggedAsset(event)) {
    return;
  }
  isPlatformDragOver.value = true;
  previewPlatformDropPosition(event);
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = "copy";
  }
}

function onPlatformDrop(event: DragEvent) {
  const asset = findDraggedAsset(event);
  isPlatformDragOver.value = false;
  if (!asset) {
    return;
  }
  const textarea = previewPlatformDropPosition(event);
  if (textarea && platformDropIndex.value !== null) {
    textarea.setSelectionRange(platformDropIndex.value, platformDropIndex.value);
  }
  insertAssetReference(asset, textarea, activePreviewText);
  platformDropIndex.value = null;
  dragState.value = null;
}

function onPlatformDragLeave(event: DragEvent) {
  const current = event.currentTarget as HTMLElement;
  const related = event.relatedTarget as Node | null;
  if (!related || !current.contains(related)) {
    isPlatformDragOver.value = false;
    platformDropIndex.value = null;
  }
}

function onDragStart(tab: MediaTab, index: number, event: DragEvent) {
  dragState.value = { tab, fromIndex: index, overIndex: index, position: "before" };
  const asset = assets.value[tab][index];
  if (asset) {
    event.dataTransfer?.setData("text/plain", assetMarker(asset));
    event.dataTransfer?.setData("application/x-auto-upt-asset", JSON.stringify({ tab, index, id: asset.id }));
  }
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "copyMove";
  }
}

function onDragOver(tab: MediaTab, index: number, event: DragEvent) {
  if (!dragState.value || dragState.value.tab !== tab) {
    return;
  }

  const target = event.currentTarget as HTMLElement;
  const rect = target.getBoundingClientRect();
  const isHorizontal = tab !== "audios";
  const midpoint = isHorizontal ? rect.left + rect.width / 2 : rect.top + rect.height / 2;
  const pointer = isHorizontal ? event.clientX : event.clientY;
  dragState.value = {
    ...dragState.value,
    overIndex: index,
    position: pointer < midpoint ? "before" : "after"
  };
}

function onListDragOver(tab: MediaTab, event: DragEvent) {
  if (!dragState.value || dragState.value.tab !== tab) {
    return;
  }

  const list = event.currentTarget as HTMLElement;
  const cards = Array.from(list.querySelectorAll<HTMLElement>(".media-card"));
  if (!cards.length) {
    return;
  }

  const isHorizontal = tab !== "audios";
  const pointer = isHorizontal ? event.clientX : event.clientY;
  let nearestCard = cards[0];
  let nearestDistance = Number.POSITIVE_INFINITY;

  for (const card of cards) {
    const rect = card.getBoundingClientRect();
    const start = isHorizontal ? rect.left : rect.top;
    const end = isHorizontal ? rect.right : rect.bottom;
    const center = start + (end - start) / 2;
    const distance = pointer < start ? start - pointer : pointer > end ? pointer - end : Math.abs(pointer - center);
    if (distance < nearestDistance) {
      nearestCard = card;
      nearestDistance = distance;
    }
  }

  const rect = nearestCard.getBoundingClientRect();
  const midpoint = isHorizontal ? rect.left + rect.width / 2 : rect.top + rect.height / 2;
  const index = Number(nearestCard.dataset.index);
  if (Number.isNaN(index)) {
    return;
  }

  dragState.value = {
    ...dragState.value,
    overIndex: index,
    position: pointer < midpoint ? "before" : "after"
  };
}

function onDrop(tab: MediaTab) {
  if (!dragState.value || dragState.value.tab !== tab) {
    dragState.value = null;
    return;
  }

  const list = assets.value[tab];
  const moving = list[dragState.value.fromIndex];
  if (!moving) {
    dragState.value = null;
    return;
  }

  const [item] = list.splice(dragState.value.fromIndex, 1);
  let insertIndex = dragState.value.overIndex + (dragState.value.position === "after" ? 1 : 0);
  if (dragState.value.fromIndex < insertIndex) {
    insertIndex -= 1;
  }
  list.splice(Math.max(0, Math.min(insertIndex, list.length)), 0, item);
  dragState.value = null;
}

function dropClass(tab: MediaTab, index: number) {
  if (!dragState.value || dragState.value.tab !== tab || dragState.value.overIndex !== index || dragState.value.fromIndex === index) {
    return "";
  }

  return dragState.value.position === "before" ? "is-drop-before" : "is-drop-after";
}
</script>

<template>
  <section class="editor-view">
    <div class="section-title">
      <div>
        <p>内容编辑</p>
        <h2>统一内容编辑区</h2>
      </div>
      <el-tag type="info">{{ wordCount }} 字</el-tag>
    </div>

    <el-form label-position="top">
      <div class="title-cover-row">
        <div class="title-tag-fields">
          <el-form-item label="标题">
            <el-input v-model="title" :prefix-icon="EditPen" maxlength="64" show-word-limit placeholder="请输入标题，留空时将自动生成" />
          </el-form-item>

          <el-form-item label="关键词">
            <el-input v-model="tags" placeholder="多个关键词，逗号分隔" />
          </el-form-item>
        </div>

        <el-form-item label="封面图" class="cover-form-item">
          <div class="cover-picker">
            <el-upload
              v-if="!assets.coverImage"
              class="cover-upload"
              drag
              :auto-upload="false"
              :limit="1"
              accept="image/*"
              :show-file-list="false"
              :on-change="onCoverChange"
            >
              <div class="cover-add">
                <el-icon><Plus /></el-icon>
                <span>上传封面图</span>
              </div>
            </el-upload>
            <div v-else class="cover-preview">
              <img :src="assets.coverImage.previewUrl" :alt="assets.coverImage.name" />
              <div class="cover-meta">
                <span>{{ assets.coverImage.name }}</span>
                <el-button text type="danger" :icon="Delete" @click="clearCoverImage" />
              </div>
            </div>
          </div>
        </el-form-item>
      </div>

      <el-form-item label="正文">
        <div
          class="content-drop-zone"
          :class="{ 'is-content-drag-over': isContentDragOver }"
          @dragenter.prevent="onContentDragOver"
          @dragover.prevent="onContentDragOver"
          @dragleave="onContentDragLeave"
          @drop.prevent="onContentDrop"
        >
          <el-input v-model="content" type="textarea" :rows="15" resize="none" placeholder="请粘贴或输入正文内容，支持 Markdown 格式。" />
          <div v-if="isContentDragOver" class="content-drop-hint">释放鼠标，将素材插入到光标位置</div>
        </div>
      </el-form-item>

      <el-form-item label="多媒体">
        <el-tabs class="media-tabs" model-value="images">
          <el-tab-pane v-for="tab in mediaTabs" :key="tab.key" :label="tab.label" :name="tab.key">
            <div
              class="media-list"
              :class="`media-list-${tab.key}`"
              @dragover.prevent="onListDragOver(tab.key, $event)"
              @drop="onDrop(tab.key)"
              @dragleave.self="dragState = null"
            >
              <el-upload
                class="media-add"
                drag
                multiple
                :auto-upload="false"
                :accept="tab.accept"
                :show-file-list="false"
                :on-change="createChangeHandler(tab.key)"
              >
                <div class="add-tile">
                  <el-icon><Plus /></el-icon>
                  <span>{{ tab.addText }}</span>
                </div>
              </el-upload>

              <article
                v-for="(asset, index) in assets[tab.key]"
                :key="asset.id"
                class="media-card"
                :class="[`media-card-${asset.kind}`, dropClass(tab.key, index)]"
                :data-index="index"
                draggable="true"
                @dragstart="onDragStart(tab.key, index, $event)"
                @dragover.prevent="onDragOver(tab.key, index, $event)"
                @drop.prevent="onDrop(tab.key)"
                @dragend="dragState = null"
              >
                <div class="media-preview">
                  <img v-if="asset.kind === 'image'" :src="asset.previewUrl" :alt="asset.name" />
                  <video v-else-if="asset.kind === 'video'" :src="asset.previewUrl" controls />
                  <audio v-else :src="asset.previewUrl" controls />
                </div>

                <div class="media-info">
                  <strong>{{ asset.name }}</strong>
                  <small>{{ (asset.size / 1024 / 1024).toFixed(2) }} MB</small>
                </div>

                <div class="media-actions">
                  <el-button text type="primary" :icon="Plus" @click="insertAssetReference(asset)">
                    插入正文
                  </el-button>
                  <el-button text type="danger" :icon="Delete" @click="removeAsset(tab.key, index)" />
                </div>
              </article>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-form-item>

      <div class="asset-strip">
        <el-icon><MagicStick /></el-icon>
        <span>已选择 {{ assetCount }} 个素材。可拖拽调整顺序，封面图将在发布时优先使用。</span>
      </div>

      <el-form-item label="平台预览">
        <section class="platform-preview-box">
          <div class="platform-preview-tabs">
            <el-radio-group v-model="activePreviewPlatform" size="default">
              <el-radio-button v-for="option in platformOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </el-radio-button>
            </el-radio-group>
          </div>

          <div
            class="content-drop-zone"
            :class="{ 'is-content-drag-over': isPlatformDragOver }"
            @dragenter.prevent="onPlatformDragOver"
            @dragover.prevent="onPlatformDragOver"
            @dragleave="onPlatformDragLeave"
            @drop.prevent="onPlatformDrop"
          >
            <el-input
              v-model="activePreviewTitle"
              class="platform-title-box"
              placeholder="平台适配标题"
            />
            <el-input
              v-model="activePreviewTags"
              class="platform-keyword-box"
              placeholder="多个关键词，逗号分隔"
            />
            <el-input
              v-model="activePreviewText"
              type="textarea"
              :rows="12"
              resize="none"
              placeholder="点击「生成预览」后，此处将显示当前平台的适配内容，支持直接编辑和拖放素材。"
            />
            <div v-if="isPlatformDragOver" class="content-drop-hint">释放鼠标，将素材插入到光标位置</div>
          </div>

          <div v-if="activePreviewDraft?.assets?.length" class="platform-media-strip">
            <span class="platform-media-label">已关联素材</span>
            <div
              v-for="(rawAsset, index) in activePreviewDraft.assets"
              :key="index"
              class="platform-media-thumb"
            >
              <template v-if="(rawAsset as DraftAssetEntry).type === 'image' || (rawAsset as DraftAssetEntry).type === 'cover'">
                <img
                  :src="(rawAsset as DraftAssetEntry).preview_url || (rawAsset as DraftAssetEntry).url"
                  :alt="(rawAsset as DraftAssetEntry).name"
                />
              </template>
              <video
                v-else-if="(rawAsset as DraftAssetEntry).type === 'video'"
                :src="(rawAsset as DraftAssetEntry).preview_url || (rawAsset as DraftAssetEntry).url"
              />
              <span v-else class="platform-media-icon">{{ (rawAsset as DraftAssetEntry).name }}</span>
            </div>
          </div>

          <div class="platform-preview-actions">
            <span>{{ activePreviewDraft ? "当前平台草稿已生成，可直接编辑或拖放素材。" : "当前平台暂无预览内容。" }}</span>
            <div class="platform-preview-btns">
              <el-button
                :disabled="!hasPreview"
                @click="$emit('openPreview', activePreviewPlatform)"
              >
                查看当前预览
              </el-button>
              <el-button
                type="success"
                :icon="MagicStick"
                :loading="agentLoading"
                :disabled="!hasPreview || !content.trim()"
                @click="$emit('optimizeWithAgent', activePreviewPlatform)"
              >
                Agent 优化
              </el-button>
            </div>
          </div>
        </section>
      </el-form-item>

      <el-form-item label="平台" class="platform-before-actions">
        <el-checkbox-group v-model="platforms" class="platforms">
          <el-checkbox-button v-for="option in platformOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </el-checkbox-button>
        </el-checkbox-group>
      </el-form-item>
    </el-form>

    <div class="action-row">
      <el-button type="primary" :icon="Connection" :loading="previewLoading" @click="$emit('generatePreview')">
        生成预览
      </el-button>
      <el-button type="success" :icon="MagicStick" :loading="agentLoading" :disabled="!content.trim()" @click="$emit('optimizeAllWithAgent')">
        一键 Agent 优化
      </el-button>
      <el-button :disabled="!hasPreview" @click="$emit('openPreview')">
        多平台预览
      </el-button>
      <el-button type="primary" :icon="Promotion" :disabled="!hasPreview" @click="$emit('confirmPublish')">
        发布
      </el-button>
    </div>
  </section>
</template>

<style scoped>
.editor-view {
  min-width: 0;
  padding: 22px;
  background: #ffffff;
  border: 1px solid #dfe5ee;
  border-radius: 8px;
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

.title-cover-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 176px;
  align-items: stretch;
  gap: 14px;
  width: 100%;
}

.title-tag-fields {
  min-width: 0;
}

.cover-form-item {
  margin-bottom: 18px;
}

.cover-picker,
.cover-upload,
.cover-upload :deep(.el-upload),
.cover-upload :deep(.el-upload-dragger) {
  width: 100%;
}

.cover-upload :deep(.el-upload-dragger) {
  display: grid;
  place-items: center;
  height: 118px;
  padding: 0;
}

.cover-add {
  display: grid;
  place-items: center;
  gap: 6px;
  color: #4f6279;
  font-size: 12px;
}

.cover-add .el-icon {
  color: #1f6feb;
  font-size: 22px;
}

.cover-preview {
  overflow: hidden;
  background: #f8fafc;
  border: 1px solid #e2eaf3;
  border-radius: 8px;
}

.cover-preview img {
  display: block;
  width: 100%;
  height: 92px;
  object-fit: cover;
}

.cover-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-height: 26px;
  padding: 4px 6px;
  color: #4f6279;
  font-size: 12px;
}

.cover-meta span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.platforms,
.media-list,
.media-actions,
.action-row,
.asset-strip {
  display: flex;
  align-items: center;
}

.platforms,
.action-row {
  flex-wrap: wrap;
  gap: 8px;
}

.platform-before-actions {
  margin-bottom: 14px;
}

.platforms :deep(.el-checkbox-button__inner) {
  border-radius: 8px;
  border-left: 1px solid var(--el-border-color);
}

.content-drop-zone {
  position: relative;
  width: 100%;
  border-radius: 8px;
}

.content-drop-zone .platform-title-box,
.content-drop-zone .platform-keyword-box {
  margin-bottom: 8px;
}

.content-drop-zone :deep(.el-textarea__inner) {
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    background-color 0.15s ease;
}

.content-drop-zone.is-content-drag-over :deep(.el-textarea__inner) {
  background: #f8fbff;
  border-color: #1f6feb;
  box-shadow: 0 0 0 3px rgba(31, 111, 235, 0.12);
}

.content-drop-hint {
  position: absolute;
  right: 12px;
  bottom: 12px;
  pointer-events: none;
  padding: 5px 8px;
  color: #1f6feb;
  background: #ffffff;
  border: 1px solid #b8d3ff;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(23, 32, 51, 0.12);
  font-size: 12px;
}

.platform-preview-box {
  display: grid;
  gap: 12px;
  width: 100%;
  padding: 14px;
  background: #f8fafc;
  border: 1px solid #e2eaf3;
  border-radius: 8px;
}

.platform-preview-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.platform-preview-tabs :deep(.el-radio-button__inner) {
  border-radius: 8px;
  border-left: 1px solid var(--el-border-color);
}

.platform-preview-box :deep(.el-textarea__inner),
.platform-keyword-box :deep(.el-input__inner),
.platform-title-box :deep(.el-input__inner) {
  background: #ffffff;
  color: #253247;
}

.platform-preview-box :deep(.el-textarea__inner::placeholder),
.platform-keyword-box :deep(.el-input__inner::placeholder),
.platform-title-box :deep(.el-input__inner::placeholder) {
  color: #9aa9bb;
}

.platform-preview-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.platform-preview-actions span {
  color: #607086;
  font-size: 13px;
}

.media-tabs {
  width: 100%;
}

.media-list {
  align-items: stretch;
  flex-wrap: wrap;
  gap: 12px;
  min-height: 110px;
  padding: 4px;
  border-radius: 8px;
}

.media-list-audios {
  display: grid;
  grid-template-columns: 1fr;
}

.media-add,
.media-card-image,
.media-card-video {
  width: 144px;
  min-height: 170px;
}

.media-list-audios .media-add {
  width: auto;
  min-height: 86px;
}

.media-add :deep(.el-upload),
.media-add :deep(.el-upload-dragger) {
  width: 100%;
  height: 100%;
}

.media-add :deep(.el-upload-dragger) {
  display: grid;
  place-items: center;
  min-height: 170px;
  padding: 0;
}

.media-list-audios .media-add :deep(.el-upload-dragger) {
  min-height: 86px;
}

.add-tile {
  display: grid;
  place-items: center;
  gap: 8px;
  color: #4f6279;
  font-size: 14px;
}

.add-tile .el-icon {
  color: #1f6feb;
  font-size: 24px;
}

.media-card {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 10px;
  cursor: grab;
  background: #f8fafc;
  border: 1px solid #e2eaf3;
  border-radius: 8px;
  box-shadow: 0 1px 0 rgba(23, 32, 51, 0.03);
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.15s ease;
}

.media-card:active {
  cursor: grabbing;
}

.media-card.is-drop-before,
.media-card.is-drop-after {
  border-color: #b8d3ff;
  box-shadow: 0 0 0 3px rgba(31, 111, 235, 0.08);
}

.media-card.is-drop-before::before,
.media-card.is-drop-after::after {
  position: absolute;
  z-index: 2;
  content: "";
  background: #1f6feb;
  border-radius: 999px;
  box-shadow: 0 0 0 3px rgba(31, 111, 235, 0.14);
}

.media-card-image.is-drop-before::before,
.media-card-video.is-drop-before::before,
.media-card-image.is-drop-after::after,
.media-card-video.is-drop-after::after {
  top: 10px;
  bottom: 10px;
  width: 3px;
}

.media-card-image.is-drop-before::before,
.media-card-video.is-drop-before::before {
  left: -8px;
}

.media-card-image.is-drop-after::after,
.media-card-video.is-drop-after::after {
  right: -8px;
}

.media-card-audio.is-drop-before::before,
.media-card-audio.is-drop-after::after {
  right: 12px;
  left: 12px;
  height: 3px;
}

.media-card-audio.is-drop-before::before {
  top: -7px;
}

.media-card-audio.is-drop-after::after {
  bottom: -7px;
}

.media-card-audio {
  display: grid;
  grid-template-columns: minmax(220px, 2fr) minmax(160px, 1fr) auto;
  align-items: center;
  gap: 12px;
  width: auto;
  min-height: 86px;
  padding: 12px;
}

.media-preview {
  display: grid;
  place-items: center;
  height: 92px;
  overflow: hidden;
  background: #eef3f8;
  border: 1px solid #e6edf5;
  border-radius: 8px;
}

.media-preview img,
.media-preview video {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.media-preview audio {
  width: 100%;
}

.media-card-audio .media-preview {
  height: auto;
  min-height: 40px;
  padding: 0;
  background: transparent;
  border: 0;
  border-radius: 0;
}

.media-info {
  min-width: 0;
  padding: 9px 0 6px;
}

.media-info strong,
.media-info small {
  display: block;
}

.media-info strong {
  overflow: hidden;
  color: #253247;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.media-info small {
  margin-top: 3px;
  color: #607086;
  font-size: 12px;
}

.media-actions {
  justify-content: flex-end;
  gap: 4px;
  margin-top: auto;
}

.media-card-audio .media-info {
  padding: 0;
}

.media-card-audio .media-info strong {
  font-size: 12px;
}

.media-card-audio .media-actions {
  margin-top: 0;
}

.action-row {
  margin-bottom: 14px;
}

.platform-media-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.platform-media-label {
  color: #607086;
  font-size: 13px;
  flex-shrink: 0;
}

.platform-media-thumb {
  width: 48px;
  height: 48px;
  overflow: hidden;
  border-radius: 6px;
  border: 1px solid #e2eaf3;
  background: #f7f9fc;
  display: grid;
  place-items: center;
}

.platform-media-thumb img,
.platform-media-thumb video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.platform-media-icon {
  color: #607086;
  font-size: 10px;
  text-align: center;
  word-break: break-all;
  padding: 2px;
}

.platform-preview-btns {
  display: flex;
  gap: 8px;
}

.asset-strip {
  gap: 8px;
  padding: 12px 14px;
  color: #4f6279;
  background: #eef3f8;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
}

@media (max-width: 760px) {
  .media-list-audios {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .title-cover-row {
    grid-template-columns: 1fr;
  }

  .media-add,
  .media-card-image,
  .media-card-video,
  .media-card {
    width: 100%;
  }

  .media-card-audio {
    grid-template-columns: 1fr;
  }
}
</style>
