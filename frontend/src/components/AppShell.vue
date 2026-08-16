<template>
  <div class="app-shell">
    <header class="app-shell-header">
      <h1 class="app-shell-title">AI 直播运营助手</h1>
      <span v-if="session.loaded" class="app-shell-session">
        {{ session.user ? `已登录：${session.user.username}` : "未登录" }}
      </span>
    </header>
    <main class="app-shell-main">
      <slot />
    </main>
  </div>
</template>

<script setup>
// 基础布局壳：仅承载页头与会话状态，占位风格从简，不做视觉重设计。
import { onMounted } from "vue";
import { session, loadSession } from "../state/session";

onMounted(loadSession);
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.app-shell-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 24px;
  border-bottom: 1px solid #e5e7eb;
  background: #fafafa;
}
.app-shell-title {
  margin: 0;
  font-size: 17px;
  color: #333;
}
.app-shell-session {
  font-size: 13px;
  color: #777;
}
.app-shell-main {
  flex: 1;
}
</style>
