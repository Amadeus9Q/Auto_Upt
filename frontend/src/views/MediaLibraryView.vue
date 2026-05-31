<script setup lang="ts">
import MediaLibraryPanel from "@/components/MediaLibraryPanel.vue";
import type { EditorAssets, MediaFolder } from "@/types/media";

const assets = defineModel<EditorAssets>("assets", { required: true });
const folders = defineModel<MediaFolder[]>("folders", { required: true });
</script>

<template>
  <section class="media-library-view">
    <MediaLibraryPanel
      v-model:assets="assets"
      v-model:folders="folders"
      title="全部多媒体资料"
      :insert-enabled="false"
    />
  </section>
</template>

<style scoped>
.media-library-view {
  min-height: calc(100vh - 160px);
}
</style>
