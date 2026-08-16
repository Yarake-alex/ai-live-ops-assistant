<template>
  <div class="app-shell">
    <header class="app-shell-header">
      <h1 class="app-shell-title">AI 直播运营助手</h1>
      <div class="app-shell-right">
        <span v-if="session.loaded" class="app-shell-session">
          {{ session.user ? `已登录：${session.user.username}` : "未登录" }}
        </span>
        <template v-if="session.user">
          <button class="header-btn" @click="cpVisible = true">修改密码</button>
          <button class="header-btn" @click="onLogout">退出登录</button>
        </template>
      </div>
    </header>
    <main class="app-shell-main">
      <slot />
    </main>

    <ChangePasswordModal v-if="cpVisible" @close="cpVisible = false" />
  </div>
</template>

<script setup>
// 基础布局壳：页头承载标题与会话状态（登录用户显示 修改密码 / 退出登录）。
// 会话恢复由 App.vue 统一处理，此处仅消费会话状态。
import { ref } from "vue";
import { session, logout } from "../state/session";
import ChangePasswordModal from "./ChangePasswordModal.vue";

const cpVisible = ref(false);

async function onLogout() {
  await logout();
}
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
  flex-wrap: wrap;
  padding: 12px 24px;
  border-bottom: 1px solid #e5e7eb;
  background: #fafafa;
}
.app-shell-title {
  margin: 0;
  font-size: 17px;
  color: #333;
}
.app-shell-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.app-shell-session {
  font-size: 13px;
  color: #777;
}
.app-shell-main {
  flex: 1;
}
</style>
