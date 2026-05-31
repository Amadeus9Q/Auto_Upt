<script setup lang="ts">
import { computed, ref } from "vue";
import type { UploadFile, UploadProps } from "element-plus";
import { Back, Delete, FolderAdd, FolderOpened, Plus, UploadFilled } from "@element-plus/icons-vue";

import type { EditorAssets, LocalAsset, MediaFolder, MediaKind, MediaTab } from "@/types/media";

interface DragState {
  tab: MediaTab;
  fromIndex: number;
  overIndex: number;
  position: "before" | "after";
}

const props = withDefaults(defineProps<{
  compact?: boolean;
  insertEnabled?: boolean;
  title?: string;
}>(), {
  compact: false,
  insertEnabled: true,
  title: "多媒体库"
});

const emit = defineEmits<{
  insert: [asset: LocalAsset];
}>();

const assets = defineModel<EditorAssets>("assets", { required: true });
const folders = defineModel<MediaFolder[]>("folders", { required: true });

const mediaTabs: Array<{ key: MediaTab; label: string; accept: string; addText: string }> = [
  { key: "images", label: "图片", accept: "image/*", addText: "添加图片" },
  { key: "videos", label: "视频", accept: "video/*", addText: "添加视频" },
  { key: "audios", label: "音频", accept: "audio/*", addText: "添加音频" }
];

const activeTab = ref<MediaTab>("images");
const activeFolderId = ref<string | null>(null);
const dragState = ref<DragState | null>(null);

const assetCount = computed(() => assets.value.images.length + assets.value.videos.length + assets.value.audios.length);
const activeFolderName = computed(() => folders.value.find((folder) => folder.id === activeFolderId.value)?.name ?? "全部素材");
const parentFolderId = computed(() => folders.value.find((folder) => folder.id === activeFolderId.value)?.parentId ?? null);
const childFolders = computed(() => folders.value.filter((folder) => folder.parentId === activeFolderId.value));
const folderTrail = computed(() => {
  const trail: MediaFolder[] = [];
  let cursor = activeFolderId.value;
  while (cursor) {
    const folder = folders.value.find((item) => item.id === cursor);
    if (!folder) break;
    trail.unshift(folder);
    cursor = folder.parentId;
  }
  return trail;
});

function kindFromTab(tab: MediaTab): MediaKind {
  return tab === "images" ? "image" : tab === "videos" ? "video" : "audio";
}

function tabFromKind(kind: MediaKind): MediaTab {
  if (kind === "image") return "images";
  if (kind === "video") return "videos";
  return "audios";
}

function createAsset(file: File, tab: MediaTab): LocalAsset {
  const kind = kindFromTab(tab);
  return {
    id: `${kind}-${file.name}-${file.size}-${file.lastModified}-${crypto.randomUUID()}`,
    name: file.name,
    size: file.size,
    mimeType: file.type || "application/octet-stream",
    previewUrl: URL.createObjectURL(file),
    kind,
    file,
    folderId: activeFolderId.value ?? undefined
  };
}

function createChangeHandler(tab: MediaTab): UploadProps["onChange"] {
  return (file: UploadFile) => {
    if (!file.raw) return;
    const asset = createAsset(file.raw, tab);
    const list = assets.value[tab];
    const existing = list.find((item) => item.name === asset.name && item.size === asset.size && item.mimeType === asset.mimeType);
    if (existing) {
      existing.folderId = activeFolderId.value ?? undefined;
      return;
    }
    list.push(asset);
  };
}

function visibleAssets(tab: MediaTab) {
  if (!activeFolderId.value) return assets.value[tab];
  return assets.value[tab].filter((asset) => asset.folderId === activeFolderId.value);
}

function assetMarker(asset: LocalAsset) {
  const kindLabel: Record<MediaKind, string> = {
    image: "图片",
    video: "视频",
    audio: "音频"
  };
  return `【${kindLabel[asset.kind]}：${asset.name}】`;
}

function removeAsset(asset: LocalAsset) {
  const tab = tabFromKind(asset.kind);
  const index = assets.value[tab].findIndex((item) => item.id === asset.id);
  if (index < 0) return;
  assets.value[tab].splice(index, 1);
  if (tab === "images" && asset.id === assets.value.coverImageId) {
    assets.value.coverImageId = null;
  }
}

function createFolder(parentId = activeFolderId.value) {
  const name = window.prompt("文件夹名称");
  if (!name?.trim()) return;
  folders.value.push({
    id: `folder-${Date.now()}-${crypto.randomUUID()}`,
    name: name.trim(),
    parentId,
    createdAt: new Date().toISOString()
  });
}

function removeFolder(folder: MediaFolder) {
  const childIds = collectFolderIds(folder.id);
  const confirmed = window.confirm(`删除「${folder.name}」文件夹？其中的素材会移回上一级。`);
  if (!confirmed) return;
  folders.value = folders.value.filter((item) => !childIds.includes(item.id));
  for (const tab of ["images", "videos", "audios"] as MediaTab[]) {
    for (const asset of assets.value[tab]) {
      if (asset.folderId && childIds.includes(asset.folderId)) {
        asset.folderId = folder.parentId ?? undefined;
      }
    }
  }
  activeFolderId.value = folder.parentId;
}

function collectFolderIds(folderId: string): string[] {
  const result = [folderId];
  for (const child of folders.value.filter((item) => item.parentId === folderId)) {
    result.push(...collectFolderIds(child.id));
  }
  return result;
}

function moveAssetToCurrentFolder(asset: LocalAsset) {
  asset.folderId = activeFolderId.value ?? undefined;
}

function onDragStart(tab: MediaTab, asset: LocalAsset, event: DragEvent) {
  const index = assets.value[tab].findIndex((item) => item.id === asset.id);
  if (index < 0) return;
  dragState.value = { tab, fromIndex: index, overIndex: index, position: "before" };
  event.dataTransfer?.setData("text/plain", assetMarker(asset));
  event.dataTransfer?.setData("application/x-auto-upt-asset", JSON.stringify({ tab, index, id: asset.id }));
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "copyMove";
  }
}

function onDragOver(tab: MediaTab, asset: LocalAsset, event: DragEvent) {
  if (!dragState.value || dragState.value.tab !== tab) return;
  const index = assets.value[tab].findIndex((item) => item.id === asset.id);
  if (index < 0) return;
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
  if (dragState.value.fromIndex < insertIndex) insertIndex -= 1;
  list.splice(Math.max(0, Math.min(insertIndex, list.length)), 0, item);
  dragState.value = null;
}

function dropClass(tab: MediaTab, asset: LocalAsset) {
  const index = assets.value[tab].findIndex((item) => item.id === asset.id);
  if (!dragState.value || dragState.value.tab !== tab || dragState.value.overIndex !== index || dragState.value.fromIndex === index) {
    return "";
  }
  return dragState.value.position === "before" ? "is-drop-before" : "is-drop-after";
}
</script>

<template>
  <section class="media-library-panel" :class="{ 'is-compact': compact }">
    <header class="library-header">
      <div>
        <p>素材管理</p>
        <h2>{{ title }}</h2>
      </div>
      <el-tag type="info">{{ assetCount }} 个素材</el-tag>
    </header>

    <div class="folder-toolbar">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item>
          <button class="folder-link" type="button" @click="activeFolderId = null">全部素材</button>
        </el-breadcrumb-item>
        <el-breadcrumb-item v-for="folder in folderTrail" :key="folder.id">
          <button class="folder-link" type="button" @click="activeFolderId = folder.id">{{ folder.name }}</button>
        </el-breadcrumb-item>
      </el-breadcrumb>
      <el-button size="small" :icon="FolderAdd" @click="createFolder()">在当前目录新建文件夹</el-button>
    </div>

    <el-tabs v-model="activeTab" class="media-tabs">
      <el-tab-pane v-for="tab in mediaTabs" :key="tab.key" :label="tab.label" :name="tab.key">
        <div class="folder-context">
          <span>{{ activeFolderName }}</span>
          <small>上传的素材会保存到当前文件夹</small>
        </div>

        <div class="media-list" :class="`media-list-${tab.key}`" @drop="onDrop(tab.key)" @dragleave.self="dragState = null">
          <el-upload class="media-add" drag multiple :auto-upload="false" :accept="tab.accept" :show-file-list="false" :on-change="createChangeHandler(tab.key)">
            <div class="add-tile">
              <el-icon><UploadFilled /></el-icon>
              <span>{{ tab.addText }}</span>
            </div>
          </el-upload>

          <button
            v-if="activeFolderId"
            type="button"
            class="media-unit folder-unit"
            @click="activeFolderId = parentFolderId"
          >
            <el-icon><Back /></el-icon>
            <strong>返回上一级</strong>
            <small>回到上层文件夹</small>
          </button>

          <article v-for="folder in childFolders" :key="`${tab.key}-${folder.id}`" class="media-unit folder-unit">
            <button type="button" class="folder-open-button" @click="activeFolderId = folder.id">
              <el-icon><FolderOpened /></el-icon>
              <strong>{{ folder.name }}</strong>
              <small>打开文件夹</small>
            </button>
            <el-button class="folder-delete-button" text type="danger" :icon="Delete" @click.stop="removeFolder(folder)" />
          </article>

          <article
            v-for="asset in visibleAssets(tab.key)"
            :key="asset.id"
            class="media-card"
            :class="[`media-card-${asset.kind}`, dropClass(tab.key, asset)]"
            draggable="true"
            @dragstart="onDragStart(tab.key, asset, $event)"
            @dragover.prevent="onDragOver(tab.key, asset, $event)"
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
              <el-button v-if="insertEnabled" text type="primary" :icon="Plus" @click="emit('insert', asset)">插入正文</el-button>
              <el-button v-if="(asset.folderId ?? null) !== activeFolderId" text @click="moveAssetToCurrentFolder(asset)">移入此处</el-button>
              <el-button text type="danger" :icon="Delete" @click="removeAsset(asset)" />
            </div>
          </article>

          <el-empty v-if="!visibleAssets(tab.key).length && !childFolders.length" class="media-empty" description="当前文件夹暂无素材" />
        </div>
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.media-library-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  min-height: 0;
  padding: 18px;
  background: #ffffff;
  border: 1px solid #dfe5ee;
  border-radius: 8px;
}

.library-header,
.folder-toolbar,
.media-actions {
  display: flex;
  align-items: center;
}

.library-header {
  justify-content: space-between;
  gap: 12px;
}

.library-header p,
.library-header h2 {
  margin: 0;
}

.library-header p,
.folder-context small {
  color: #607086;
  font-size: 12px;
}

.library-header h2 {
  margin-top: 4px;
  font-size: 18px;
}

.folder-toolbar {
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2eaf3;
  border-radius: 8px;
}

.folder-link {
  padding: 0;
  color: #1f6feb;
  cursor: pointer;
  background: transparent;
  border: 0;
  font: inherit;
}

.folder-context {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.folder-context span {
  color: #253247;
  font-weight: 650;
}

.media-tabs {
  min-height: 0;
}

.media-tabs :deep(.el-tabs__content) {
  min-height: 0;
}

.media-list {
  display: flex;
  align-items: stretch;
  flex-wrap: wrap;
  gap: 12px;
  min-height: 150px;
  max-height: min(58vh, 620px);
  overflow: auto;
  padding: 4px;
  border-radius: 8px;
}

.is-compact .media-list {
  max-height: calc(100vh - 360px);
}

.media-add,
.media-unit,
.media-card-image,
.media-card-video,
.media-card-audio {
  width: 144px;
  min-height: 170px;
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

.media-unit {
  position: relative;
  display: grid;
  place-items: center;
  gap: 8px;
  padding: 14px;
  color: #253247;
  text-align: center;
  background: #f8fafc;
  border: 1px solid #e2eaf3;
  border-radius: 8px;
}

.folder-unit {
  cursor: pointer;
}

.folder-unit > .el-icon,
.folder-open-button .el-icon {
  color: #1f6feb;
  font-size: 30px;
}

.folder-unit strong,
.folder-unit small {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-unit small {
  color: #607086;
  font-size: 12px;
}

.folder-open-button {
  display: grid;
  place-items: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
  padding: 0;
  color: inherit;
  cursor: pointer;
  background: transparent;
  border: 0;
  font: inherit;
}

.folder-delete-button {
  position: absolute;
  top: 6px;
  right: 6px;
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
.media-card-audio.is-drop-before::before,
.media-card-image.is-drop-after::after,
.media-card-video.is-drop-after::after,
.media-card-audio.is-drop-after::after {
  top: 10px;
  bottom: 10px;
  width: 3px;
}

.media-card-image.is-drop-before::before,
.media-card-video.is-drop-before::before,
.media-card-audio.is-drop-before::before {
  left: -8px;
}

.media-card-image.is-drop-after::after,
.media-card-video.is-drop-after::after,
.media-card-audio.is-drop-after::after {
  right: -8px;
}

.media-card-audio {
  display: flex;
  align-items: stretch;
  gap: 0;
  padding: 10px;
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
  height: 92px;
  padding: 8px;
  background: #eef3f8;
  border: 1px solid #e6edf5;
  border-radius: 8px;
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
  flex-wrap: wrap;
}

.media-empty {
  flex: 1;
  min-width: 220px;
}

@media (max-width: 760px) {
  .media-library-panel {
    padding: 14px;
  }

}
</style>
