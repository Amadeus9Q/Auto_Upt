<script setup lang="ts">
import { computed, ref } from "vue";
import type { UploadFile, UploadFiles, UploadProps } from "element-plus";
import { Connection, Delete, EditPen, MagicStick, Plus, Upload } from "@element-plus/icons-vue";

import type { PlatformKey } from "@/api/client";

export type MediaKind = "image" | "video" | "audio";

export interface LocalAsset {
  id: string;
  name: string;
  size: number;
  mimeType: string;
  previewUrl: string;
  kind: MediaKind;
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

defineProps<{
  wordCount: number;
  previewLoading: boolean;
  taskLoading: boolean;
  hasPreview: boolean;
}>();

defineEmits<{
  generatePreview: [];
  simulatePublish: [];
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

const assetCount = computed(() => assets.value.images.length + assets.value.videos.length + assets.value.audios.length);

function kindFromTab(tab: MediaTab): MediaKind {
  return tab === "images" ? "image" : tab === "videos" ? "video" : "audio";
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
    kind: kindFromTab(tab)
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

function onDragStart(tab: MediaTab, index: number, event: DragEvent) {
  dragState.value = { tab, fromIndex: index, overIndex: index, position: "before" };
  event.dataTransfer?.setData("text/plain", `${tab}:${index}`);
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "move";
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
        <p>内容输入</p>
        <h2>统一内容 IR 草稿</h2>
      </div>
      <el-tag type="info">{{ wordCount }} 字</el-tag>
    </div>

    <el-form label-position="top">
      <div class="title-cover-row">
        <div class="title-tag-fields">
          <el-form-item label="标题">
            <el-input v-model="title" :prefix-icon="EditPen" maxlength="64" show-word-limit />
          </el-form-item>

          <el-form-item label="标签">
            <el-input v-model="tags" placeholder="用逗号或空格分隔" />
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
        <el-input v-model="content" type="textarea" :rows="15" resize="none" placeholder="粘贴 Markdown、富文本要点或视频简介。" />
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
                  <el-button text type="danger" :icon="Delete" @click="removeAsset(tab.key, index)" />
                </div>
              </article>
            </div>
          </el-tab-pane>
        </el-tabs>
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
      <el-button :icon="Upload" :disabled="!hasPreview" :loading="taskLoading" @click="$emit('simulatePublish')">
        模拟发布
      </el-button>
    </div>

    <div class="lint-strip">
      <el-icon><MagicStick /></el-icon>
      <span>已选择 {{ assetCount }} 个多媒体文件。拖拽文件卡片可调整顺序，封面图会优先用于平台发布表单。</span>
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
.lint-strip {
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
  grid-template-columns: minmax(130px, 0.7fr) minmax(300px, 2fr) auto;
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

.media-card-audio .media-actions {
  margin-top: 0;
}

.action-row {
  margin-bottom: 14px;
}

.lint-strip {
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
