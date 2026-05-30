<script setup lang="ts">
import { ChatDotRound, Document, Notebook, VideoCamera } from "@element-plus/icons-vue";

interface AccountPlatform {
  key: string;
  label: string;
  status: string;
  futureSupport: string;
  icon: typeof Document;
}

const platforms: AccountPlatform[] = [
  {
    key: "wechat",
    label: "公众号",
    status: "未接入",
    futureSupport: "后续支持草稿箱/素材上传",
    icon: Document
  },
  {
    key: "zhihu",
    label: "知乎",
    status: "未接入",
    futureSupport: "后续支持浏览器辅助发布",
    icon: ChatDotRound
  },
  {
    key: "xiaohongshu",
    label: "小红书",
    status: "未接入",
    futureSupport: "后续支持浏览器辅助发布",
    icon: Notebook
  },
  {
    key: "bilibili",
    label: "B站",
    status: "未接入",
    futureSupport: "后续支持官方 API / biliup 辅助",
    icon: VideoCamera
  }
];
</script>

<template>
  <section class="account-view">
    <div class="section-title">
      <div>
        <p>账号管理</p>
        <h2>平台账号接入状态</h2>
      </div>
      <el-tag type="info">Skeleton</el-tag>
    </div>

    <div class="account-grid">
      <article v-for="platform in platforms" :key="platform.key" class="account-card">
        <div class="account-icon">
          <el-icon :size="24">
            <component :is="platform.icon" />
          </el-icon>
        </div>
        <div class="account-content">
          <header>
            <strong>{{ platform.label }}</strong>
            <el-tag type="info">{{ platform.status }}</el-tag>
          </header>
          <p>{{ platform.futureSupport }}</p>
        </div>
      </article>
    </div>

    <el-alert
      class="phase-note"
      title="当前阶段只展示账号状态占位，不接入真实授权、不保存真实账号信息、不执行真实发布。"
      type="warning"
      show-icon
      :closable="false"
    />
  </section>
</template>

<style scoped>
.account-view {
  min-width: 0;
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

.account-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.account-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  min-width: 0;
  padding: 18px;
  background: #ffffff;
  border: 1px solid #dfe5ee;
  border-radius: 8px;
}

.account-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  flex: 0 0 auto;
  color: #2f6fed;
  background: #edf4ff;
  border-radius: 8px;
}

.account-content {
  min-width: 0;
  flex: 1;
}

.account-content header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.account-content strong {
  font-size: 17px;
}

.account-content p {
  margin: 12px 0 0;
  color: #4f6279;
  line-height: 1.55;
}

.phase-note {
  margin-top: 18px;
}

@media (max-width: 680px) {
  .account-grid {
    grid-template-columns: 1fr;
  }

  .account-content header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
