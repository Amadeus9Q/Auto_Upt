<script setup lang="ts">
import type { BodySegment } from "@/views/PreviewView.vue";

defineProps<{
  title: string;
  summary: string;
  body: string;
  tags: string[];
  bodySegments?: BodySegment[];
  coverImage?: { url?: string; name?: string } | null;
  author?: string;
  metadata?: { estimated_read_time_minutes?: number };
}>();
</script>

<template>
  <div class="wechat-phone-frame">
    <!-- 顶部状态栏 -->
    <div class="phone-status-bar">
      <span class="carrier">中国移动</span>
      <span class="time">12:00</span>
      <span class="battery">100%</span>
    </div>

    <!-- 公众号导航栏 -->
    <div class="wechat-nav">
      <span class="nav-back">‹</span>
      <span class="nav-title">公众号</span>
      <span class="nav-more">···</span>
    </div>

    <!-- 文章标题区 -->
    <div class="article-header">
      <h1 class="article-title">{{ title }}</h1>
      <div class="article-meta">
        <span class="meta-author">{{ author || 'Auto_Upt' }}</span>
        <span class="meta-time">{{ metadata?.estimated_read_time_minutes || 1 }} 分钟</span>
      </div>
    </div>

    <!-- 正文（从 body 解析渲染） -->
    <div class="article-body">
      <template v-if="bodySegments?.length">
        <template v-for="(segment, idx) in bodySegments" :key="idx">
          <div v-if="segment.type === 'image'" class="wx-image">
            <img v-if="segment.src" :src="segment.src" :alt="segment.name || '图片'" class="wx-media-img" />
            <div v-else class="wx-image-placeholder">
              <span>📷 {{ segment.name || '图片' }}</span>
            </div>
            <p v-if="segment.name">{{ segment.name }}</p>
          </div>
          <div v-else-if="segment.type === 'video'" class="wx-link-card">
            <span class="wx-link-card-icon">视频号</span>
            <strong>{{ segment.name || '视频素材' }}</strong>
            <p>公众号正文不支持直接嵌入视频，请替换为外链或视频号卡片。</p>
          </div>
          <div v-else-if="segment.type === 'audio'" class="wx-link-card">
            <span class="wx-link-card-icon">外链</span>
            <strong>{{ segment.name || '音频素材' }}</strong>
            <p>公众号正文不支持直接嵌入音频，请替换为外链或视频号卡片。</p>
          </div>
          <p v-else class="wx-paragraph">{{ segment.text }}</p>
        </template>
      </template>
      <pre v-else class="wx-fallback">{{ body }}</pre>
    </div>

    <!-- 标签 -->
    <div v-if="tags.length" class="article-tags">
      <span v-for="tag in tags" :key="tag" class="wx-tag">#{{ tag }}</span>
    </div>

    <!-- 底部 -->
    <div class="article-footer">
      <span>阅读 {{ metadata?.estimated_read_time_minutes || 1 }} 分钟</span>
    </div>
  </div>
</template>

<style scoped>
.wechat-phone-frame {
  width: 375px;
  max-width: 100%;
  margin: 0 auto;
  border: 1px solid #dcdcdc;
  border-radius: 20px;
  overflow: hidden;
  background: #ffffff;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.12);
  font-family:
    -apple-system, BlinkMacSystemFont, "PingFang SC", "Helvetica Neue",
    "Microsoft YaHei", sans-serif;
  color: #3e3e3e;
}

/* ── 状态栏 ── */
.phone-status-bar {
  display: flex;
  justify-content: space-between;
  padding: 8px 18px 4px;
  background: #ededed;
  font-size: 11px;
  font-weight: 500;
  color: #1a1a1a;
}

/* ── 导航栏 ── */
.wechat-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #ededed;
  font-size: 17px;
  font-weight: 600;
  color: #191919;
  border-bottom: 1px solid #d6d6d6;
}
.nav-back {
  font-size: 24px;
  line-height: 1;
  color: #191919;
}
.nav-more {
  font-size: 18px;
  letter-spacing: 2px;
  color: #191919;
}

/* ── 标题区 ── */
.article-header {
  padding: 22px 16px 10px;
}
.article-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  line-height: 1.35;
  color: #1a1a1a;
}
.article-meta {
  display: flex;
  gap: 12px;
  margin-top: 10px;
  font-size: 13px;
  color: #999;
}

/* ── 正文 ── */
.article-body {
  padding: 0 16px 16px;
  font-size: 16px;
  line-height: 1.8;
  color: #3e3e3e;
}
.wx-paragraph {
  margin: 0 0 14px;
}
.wx-image {
  margin: 16px 0;
  text-align: center;
}
.wx-image-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 120px;
  background: #f5f5f5;
  border: 1px dashed #d0d0d0;
  border-radius: 4px;
  font-size: 14px;
  color: #999;
}
.wx-media-img {
  display: block;
  width: 100%;
  max-height: 220px;
  object-fit: contain;
  background: #f5f5f5;
  border-radius: 4px;
}
.wx-image p {
  margin: 6px 0 0;
  font-size: 12px;
  color: #999;
}
.wx-link-card {
  margin: 16px 0;
  padding: 12px;
  background: #f6f8fa;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}
.wx-link-card-icon {
  display: inline-flex;
  margin-bottom: 8px;
  padding: 2px 6px;
  border-radius: 4px;
  background: #e8f3ff;
  color: #576b95;
  font-size: 12px;
}
.wx-link-card strong {
  display: block;
  color: #1f2937;
  font-size: 13px;
}
.wx-link-card p {
  margin: 6px 0 0;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.6;
}
.wx-fallback {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 16px;
  line-height: 1.8;
}

/* ── 标签 ── */
.article-tags {
  padding: 0 16px 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.wx-tag {
  font-size: 13px;
  color: #576b95;
}

/* ── 底部 ── */
.article-footer {
  padding: 12px 16px 18px;
  text-align: center;
  font-size: 12px;
  color: #b2b2b2;
  border-top: 1px solid #f0f0f0;
}
</style>
