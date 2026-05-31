<script setup lang="ts">
import { computed, ref } from "vue";
import type { UploadFile, UploadProps } from "element-plus";
import { Back, Delete, EditPen, FolderAdd, FolderOpened, UploadFilled } from "@element-plus/icons-vue";

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
  rename: [payload: { asset: LocalAsset; oldName: string; newName: string }];
  delete: [asset: LocalAsset];
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
const folderDragTargetId = ref<string | null>(null);
const renamingAssetId = ref<string | null>(null);
const renameValue = ref("");

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

function overwriteAsset(target: LocalAsset, source: LocalAsset) {
  target.size = source.size;
  target.mimeType = source.mimeType;
  target.previewUrl = source.previewUrl;
  target.file = source.file;
  target.backendAssetId = undefined;
  target.backendUrl = undefined;
  target.uploadPurpose = undefined;
}

function findSameNameAsset(tab: MediaTab, name: string) {
  return assets.value[tab].find((item) => item.name === name);
}

function createChangeHandler(tab: MediaTab): UploadProps["onChange"] {
  return (file: UploadFile) => {
    if (!file.raw) return;
    const asset = createAsset(file.raw, tab);
    const existing = findSameNameAsset(tab, asset.name);
    if (existing) {
      const confirmed = window.confirm(`已存在名为「${asset.name}」的素材，是否覆盖原文件？`);
      if (confirmed) {
        rememberAssetPath(existing);
        overwriteAsset(existing, asset);
      }
      return;
    }
    assets.value[tab].push(asset);
  };
}

function visibleAssets(tab: MediaTab) {
  if (!activeFolderId.value) return assets.value[tab].filter((asset) => !asset.folderId);
  return assets.value[tab].filter((asset) => asset.folderId === activeFolderId.value);
}

function assetMarker(asset: LocalAsset) {
  const kindLabel: Record<MediaKind, string> = {
    image: "图片",
    video: "视频",
    audio: "音频"
  };
  return `【${kindLabel[asset.kind]}：${assetFolderPath(asset)}】`;
}

function assetFolderPath(asset: LocalAsset) {
  const names: string[] = [];
  let cursor = asset.folderId;
  while (cursor) {
    const folder = folders.value.find((item) => item.id === cursor);
    if (!folder) break;
    names.unshift(folder.name);
    cursor = folder.parentId ?? undefined;
  }
  return [...names, asset.name].join("/");
}

function rememberAssetPath(asset: LocalAsset) {
  const path = assetFolderPath(asset);
  asset.aliasPaths = Array.from(new Set([...(asset.aliasPaths ?? []), path]));
}

function removeAsset(asset: LocalAsset) {
  const tab = tabFromKind(asset.kind);
  const index = assets.value[tab].findIndex((item) => item.id === asset.id);
  if (index < 0) return;
  emit("delete", asset);
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
  const childFolderIds = collectFolderIds(folder.id);
  // Count assets that will be deleted
  let assetDeleteCount = 0;
  for (const tab of ["images", "videos", "audios"] as MediaTab[]) {
    for (const asset of assets.value[tab]) {
      if (asset.folderId && childFolderIds.includes(asset.folderId)) {
        assetDeleteCount += 1;
      }
    }
  }

  const childFolderCount = childFolderIds.length - 1; // excluding self
  const detailParts = [`将永久删除文件夹「${folder.name}」`];
  if (childFolderCount > 0) detailParts.push(`${childFolderCount} 个子文件夹`);
  if (assetDeleteCount > 0) detailParts.push(`${assetDeleteCount} 个素材`);
  detailParts.push("此操作不可撤销。");
  const confirmed = window.confirm(detailParts.join("、") + "\n\n确定继续？");
  if (!confirmed) return;

  // Delete all child folders
  folders.value = folders.value.filter((item) => !childFolderIds.includes(item.id));

  // Delete all assets in deleted folders
  for (const tab of ["images", "videos", "audios"] as MediaTab[]) {
    assets.value[tab] = assets.value[tab].filter((asset) => {
      if (asset.folderId && childFolderIds.includes(asset.folderId)) {
        emit("delete", asset);
        // Also clear coverImageId if the deleted asset was cover
        if (tab === "images" && asset.id === assets.value.coverImageId) {
          assets.value.coverImageId = null;
        }
        return false;
      }
      return true;
    });
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

function onDragStart(tab: MediaTab, asset: LocalAsset, event: DragEvent) {
  const index = assets.value[tab].findIndex((item) => item.id === asset.id);
  if (index < 0) return;
  dragState.value = { tab, fromIndex: index, overIndex: index, position: "before" };
  event.dataTransfer?.setData("text/plain", assetMarker(asset));
  event.dataTransfer?.setData("application/x-auto-upt-asset", JSON.stringify({ tab, index, id: asset.id }));
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "move";
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

// --- Folder drag-and-drop reorganization ---

function onFolderDragStart(folder: MediaFolder, event: DragEvent) {
  event.dataTransfer?.setData("text/plain", folder.name);
  event.dataTransfer?.setData("application/x-auto-upt-folder", JSON.stringify({ id: folder.id, name: folder.name }));
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = "move";
  }
}

function onFolderDragOver(folder: MediaFolder, event: DragEvent) {
  // Accept assets and other folders
  const hasAsset = event.dataTransfer?.types.includes("application/x-auto-upt-asset");
  const hasFolder = event.dataTransfer?.types.includes("application/x-auto-upt-folder");
  if (!hasAsset && !hasFolder) return;
  // Prevent dropping a folder onto itself or its descendants
  if (hasFolder) {
    try {
      const data = JSON.parse(event.dataTransfer!.getData("application/x-auto-upt-folder"));
      if (data.id === folder.id) return;
      if (collectFolderIds(data.id).includes(folder.id)) return;
    } catch { return; }
  }
  event.preventDefault();
  folderDragTargetId.value = folder.id;
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = "move";
  }
}

function onFolderDrop(folder: MediaFolder, event: DragEvent) {
  event.preventDefault();
  folderDragTargetId.value = null;

  // Handle folder drop (reparent)
  const folderPayload = event.dataTransfer?.getData("application/x-auto-upt-folder");
  if (folderPayload) {
    try {
      const data = JSON.parse(folderPayload) as { id: string };
      const target = folders.value.find((f) => f.id === data.id);
      if (target && target.id !== folder.id && !collectFolderIds(target.id).includes(folder.id)) {
        const movingFolderIds = collectFolderIds(target.id);
        for (const t of ["images", "videos", "audios"] as MediaTab[]) {
          for (const asset of assets.value[t]) {
            if (asset.folderId && movingFolderIds.includes(asset.folderId)) {
              rememberAssetPath(asset);
            }
          }
        }
        target.parentId = folder.id;
      }
    } catch { /* ignore */ }
    dragState.value = null;
    return;
  }

  // Handle asset drop (move to folder)
  const assetPayload = event.dataTransfer?.getData("application/x-auto-upt-asset");
  if (assetPayload) {
    try {
      const data = JSON.parse(assetPayload) as { tab?: MediaTab; index?: number; id?: string };
      if (data.id) {
        for (const t of ["images", "videos", "audios"] as MediaTab[]) {
          const found = assets.value[t].find((a) => a.id === data.id);
          if (found) {
            rememberAssetPath(found);
            found.folderId = folder.id;
            break;
          }
        }
      } else if (data.tab && typeof data.index === "number") {
        const found = assets.value[data.tab]?.[data.index];
        if (found) {
          rememberAssetPath(found);
          found.folderId = folder.id;
        }
      }
    } catch { /* ignore */ }
    dragState.value = null;
    return;
  }

  dragState.value = null;
}

function onFolderDragLeave(folder: MediaFolder, event: DragEvent) {
  const current = event.currentTarget as HTMLElement;
  const related = event.relatedTarget as Node | null;
  if (!related || !current.contains(related)) {
    folderDragTargetId.value = null;
  }
}

function enableDragHandle(event: MouseEvent) {
  const handle = event.currentTarget as HTMLElement;
  const article = handle.closest("article") as HTMLElement | null;
  if (article) article.draggable = true;
}

function resetDragHandle(event: MouseEvent) {
  const handle = event.currentTarget as HTMLElement;
  const article = handle.closest("article") as HTMLElement | null;
  if (article) article.draggable = false;
}

function disableDragHandle(event: DragEvent) {
  const article = event.currentTarget as HTMLElement;
  article.draggable = false;
}

function dropClass(tab: MediaTab, asset: LocalAsset) {
  const index = assets.value[tab].findIndex((item) => item.id === asset.id);
  if (!dragState.value || dragState.value.tab !== tab || dragState.value.overIndex !== index || dragState.value.fromIndex === index) {
    return "";
  }
  return dragState.value.position === "before" ? "is-drop-before" : "is-drop-after";
}

// --- Rename ---
function findAssetById(id: string): LocalAsset | undefined {
  for (const tab of ["images", "videos", "audios"] as MediaTab[]) {
    const found = assets.value[tab].find((a) => a.id === id);
    if (found) return found;
  }
}

function startRename(asset: LocalAsset) {
  renamingAssetId.value = asset.id;
  renameValue.value = asset.name;
}

function finishRename(asset: LocalAsset) {
  const newName = renameValue.value.trim();
  if (!newName || newName === asset.name) {
    renamingAssetId.value = null;
    return;
  }
  const tab = tabFromKind(asset.kind);
  const duplicate = assets.value[tab].find((item) => item.id !== asset.id && item.name === newName);
  if (duplicate) {
    window.alert(`已存在名为「${newName}」的素材，请先处理原文件后再重命名。`);
    return;
  }
  const oldName = asset.name;
  rememberAssetPath(asset);
  asset.name = newName;
  renamingAssetId.value = null;
  emit("rename", { asset, oldName, newName });
}

function cancelRename() {
  renamingAssetId.value = null;
  renameValue.value = "";
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

          <article
            v-for="folder in childFolders"
            :key="`${tab.key}-${folder.id}`"
            class="media-unit folder-unit"
            :class="{ 'is-folder-drag-target': folderDragTargetId === folder.id }"
            draggable="false"
            @click="activeFolderId = folder.id"
            @dragstart="onFolderDragStart(folder, $event)"
            @dragover.prevent="onFolderDragOver(folder, $event)"
            @dragleave="onFolderDragLeave(folder, $event)"
            @drop.prevent="onFolderDrop(folder, $event)"
            @dragend="disableDragHandle($event); folderDragTargetId = null"
          >
            <span class="drag-handle" @mousedown="enableDragHandle" @mouseup="resetDragHandle" />
            <el-icon><FolderOpened /></el-icon>
            <strong>{{ folder.name }}</strong>
            <small>打开文件夹</small>
            <el-button class="folder-delete-button" text type="danger" :icon="Delete" @click.stop="removeFolder(folder)" />
          </article>

          <article
            v-for="asset in visibleAssets(tab.key)"
            :key="asset.id"
            class="media-card"
            :class="[`media-card-${asset.kind}`, dropClass(tab.key, asset)]"
            draggable="false"
            @dragstart="onDragStart(tab.key, asset, $event)"
            @dragover.prevent="onDragOver(tab.key, asset, $event)"
            @drop.prevent="onDrop(tab.key)"
            @dragend="disableDragHandle($event); dragState = null"
          >
            <span class="drag-handle" :class="`drag-handle-${asset.kind}`" @mousedown="enableDragHandle" @mouseup="resetDragHandle" />
            <div class="media-preview">
              <img v-if="asset.kind === 'image'" :src="asset.previewUrl" :alt="asset.name" />
              <video v-else-if="asset.kind === 'video'" :src="asset.previewUrl" controls />
              <audio v-else :src="asset.previewUrl" controls />
            </div>

            <div class="media-info">
              <template v-if="renamingAssetId === asset.id">
                <el-input
                  v-model="renameValue"
                  size="small"
                  class="rename-input"
                  @keyup.enter="finishRename(asset)"
                  @keyup.esc="cancelRename()"
                  @blur="finishRename(asset)"
                />
              </template>
              <strong v-else>{{ asset.name }}</strong>
              <small>{{ (asset.size / 1024 / 1024).toFixed(2) }} MB</small>
            </div>

            <div class="media-actions">
              <el-button class="media-rename-btn" text :icon="EditPen" @click.stop="startRename(asset)" title="重命名" />
              <el-button class="media-delete-btn" text type="danger" :icon="Delete" @click="removeAsset(asset)" />
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
.media-card-video {
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
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 10px;
  color: #253247;
  text-align: center;
  background: #f8fafc;
  border: 1px solid #e2eaf3;
  border-radius: 8px;
  box-shadow: 0 1px 0 rgba(23, 32, 51, 0.03);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.folder-unit {
  min-width: 0;
  cursor: pointer;
}

.folder-unit.is-folder-drag-target {
  outline: 2px dashed #1f6feb;
  outline-offset: 4px;
  background: rgba(31, 111, 235, 0.06);
  transform: scale(1.02);
  transition: outline 0.15s, background 0.15s, transform 0.15s;
}

.folder-unit > .el-icon {
  color: #1f6feb;
  font-size: 22px;
}

.folder-unit strong {
  overflow: hidden;
  max-width: 100%;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  line-height: 1.3;
}

.folder-unit small {
  color: #607086;
  font-size: 11px;
  line-height: 1.3;
}

.folder-delete-button {
  position: absolute;
  top: 6px;
  right: 6px;
}

/* ---- Drag handle (grip) ---- */

.drag-handle {
  position: absolute;
  bottom: 6px;
  left: 6px;
  z-index: 2;
  width: 16px;
  height: 22px;
  border-radius: 4px;
  cursor: grab;
  opacity: 0;
  transition: opacity 0.15s;
  /* 6-dot grip via repeating gradients */
  background:
    radial-gradient(circle at 4px 4px, #8799b0 1.5px, transparent 1.5px),
    radial-gradient(circle at 12px 4px, #8799b0 1.5px, transparent 1.5px),
    radial-gradient(circle at 4px 11px, #8799b0 1.5px, transparent 1.5px),
    radial-gradient(circle at 12px 11px, #8799b0 1.5px, transparent 1.5px),
    radial-gradient(circle at 4px 18px, #8799b0 1.5px, transparent 1.5px),
    radial-gradient(circle at 12px 18px, #8799b0 1.5px, transparent 1.5px);
  background-repeat: no-repeat;
}

.media-card:hover .drag-handle,
.media-unit:hover .drag-handle {
  opacity: 0.7;
}

.drag-handle:hover {
  opacity: 1 !important;
  background-color: rgba(31, 111, 235, 0.08);
}

.drag-handle:active {
  cursor: grabbing;
}

/* Audio tab: handle adapts to flat row layout */
.media-list-audios .drag-handle {
  position: relative;
  top: auto;
  left: auto;
  bottom: auto;
  flex-shrink: 0;
  margin-right: 2px;
  opacity: 0.6;
}

.media-card {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 10px;
  background: #f8fafc;
  border: 1px solid #e2eaf3;
  border-radius: 8px;
  box-shadow: 0 1px 0 rgba(23, 32, 51, 0.03);
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.15s ease;
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

/* Audio drop indicators: horizontal bars (column layout) */
.media-card-audio.is-drop-before::before,
.media-card-audio.is-drop-after::after {
  left: 10px;
  right: 10px;
  height: 3px;
  width: auto;
  top: auto;
  bottom: auto;
}

.media-card-audio.is-drop-before::before {
  top: -8px;
}

.media-card-audio.is-drop-after::after {
  bottom: -8px;
}

/* ---- Audio tab: all units full-width, flat, audio player at 70% ---- */

.media-list-audios {
  flex-direction: column;
  gap: 8px;
}

.media-list-audios .media-add {
  width: 100%;
  min-height: 58px;
}

.media-list-audios .media-add :deep(.el-upload-dragger) {
  min-height: 58px;
}

.media-list-audios .media-add .add-tile {
  flex-direction: row;
  gap: 10px;
}

.media-list-audios .media-unit {
  width: 100%;
  min-height: 58px;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
}

.media-list-audios .media-unit.folder-unit {
  justify-content: flex-start;
}

.media-list-audios .folder-unit > .el-icon,
.media-list-audios .folder-open-button .el-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.media-list-audios .folder-unit strong {
  flex-shrink: 0;
}

.media-list-audios .folder-unit small {
  flex-shrink: 0;
}

.media-list-audios .folder-delete-button {
  margin-left: auto;
  position: static;
}

.media-card-audio {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 58px;
  padding: 8px 12px;
}

.media-card-audio .media-preview {
  flex: 0 0 70%;
  height: 54px;
  padding: 0;
  background: transparent;
  border: 0;
  display: flex;
  align-items: center;
}

.media-card-audio .media-preview audio {
  width: 100%;
  height: 48px;
}

.media-card-audio .media-info {
  flex: 0 0 auto;
  min-width: 0;
  padding: 0;
  overflow: hidden;
}

.media-card-audio .media-info strong,
.media-card-audio .media-info small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.media-card-audio .media-actions {
  flex-shrink: 0;
  margin-left: auto;
  display: flex;
  gap: 2px;
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

/* Delete & rename buttons at bottom for image/video cards */
.media-card-image .media-delete-btn,
.media-card-video .media-delete-btn {
  position: absolute;
  bottom: 6px;
  right: 6px;
}

.media-card-image .media-rename-btn,
.media-card-video .media-rename-btn {
  position: absolute;
  bottom: 6px;
  right: 40px;
}

/* Inline rename input */
.rename-input {
  width: 100%;
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
