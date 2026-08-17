<template>
  <div class="app-shell">
    <!-- 桌面端：左侧悬浮岛式侧边栏 -->
    <aside class="sidebar" aria-label="主导航">
      <div class="sidebar-brand">
        <span class="brand-mark">播</span>
        <div class="brand-copy">
          <h1 class="brand-title">AI 直播运营助手</h1>
          <span class="brand-sub">直播运营工作台</span>
        </div>
      </div>

      <nav class="sidebar-nav" aria-label="业务导航">
        <button
          v-for="item in navItems"
          :key="item.key"
          :class="{ active: view === item.key }"
          :aria-current="view === item.key ? 'page' : undefined"
          @click="$emit('navigate', item.key)"
        >
          <Icon :name="item.icon" size="16" />
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <div class="sidebar-account">
        <div v-if="session.user" class="user-chip">
          <span class="user-avatar">{{ (session.user.username || "?").slice(0, 1).toUpperCase() }}</span>
          <span class="user-copy">
            <span class="user-name">{{ session.user.username }}</span>
            <span v-if="isAdmin" class="user-role">管理员</span>
          </span>
        </div>
        <div class="account-actions">
          <button class="sidebar-action" aria-label="修改密码" @click="cpVisible = true">
            <Icon name="lock" size="14" /> 修改密码
          </button>
          <button class="sidebar-action logout-action" aria-label="退出登录" @click="onLogout">
            <Icon name="logout" size="14" /> 退出登录
          </button>
        </div>
      </div>
    </aside>


    <main class="app-shell-main">
      <slot />
    </main>

    <ChangePasswordModal v-if="cpVisible" @close="cpVisible = false" />
  </div>
</template>

<script setup>
// V6：仅桌面端悬浮岛式侧边栏。
// 保持现有 view/navigate 机制、管理员入口判断与登录态行为，不引入 router 或新依赖。
import { computed, ref } from "vue";
import { session, logout } from "../state/session";
import ChangePasswordModal from "./ChangePasswordModal.vue";
import Icon from "./Icon.vue";

const props = defineProps({
  view: { type: String, default: "dashboard" },
  isAdmin: { type: Boolean, default: false },
});
const emit = defineEmits(["navigate"]);

const cpVisible = ref(false);

const navItems = computed(() => {
  const items = [
    { key: "dashboard", label: "运营工作台", icon: "chart" },
    { key: "products", label: "商品资料", icon: "box" },
    { key: "materials", label: "直播素材库", icon: "folder" },
    { key: "comments", label: "评论助手", icon: "chat" },
  ];
  if (props.isAdmin) items.push({ key: "users", label: "用户管理", icon: "users" });
  items.push({ key: "about", label: "关于", icon: "help" });
  return items;
});

async function onLogout() {
  await logout();
}
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
}

/* ── 桌面端悬浮岛 ── */
.sidebar {
  position: fixed;
  z-index: 30;
  top: 22px;
  bottom: 22px;
  left: 22px;
  width: 216px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
}
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 18px 16px;
  border-bottom: 1px solid var(--gray-100);
}
.brand-mark {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: var(--primary);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}
.brand-copy,
.user-copy {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.brand-title {
  margin: 0;
  color: var(--gray-900);
  font-size: 15px;
  font-weight: 700;
  line-height: 1.4;
  white-space: nowrap;
}
.brand-sub {
  margin-top: 1px;
  color: var(--gray-400);
  font-size: 12px;
}
.sidebar-nav {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 4px;
  padding: 14px 10px;
}
.sidebar-nav button {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 40px;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--gray-600);
  font-size: 14px;
  text-align: left;
}
.sidebar-nav button:hover:not(:disabled) {
  background: var(--gray-50);
  color: var(--gray-900);
}
.sidebar-nav button.active {
  border-color: var(--primary-border);
  background: var(--primary-soft);
  color: var(--primary);
  font-weight: 600;
}
.sidebar-account {
  padding: 14px 10px;
  border-top: 1px solid var(--gray-100);
}
.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 0 8px 12px;
}
.user-avatar {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--primary-soft);
  color: var(--primary);
  font-size: 13px;
  font-weight: 700;
}
.user-name {
  overflow: hidden;
  color: var(--gray-700);
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-role {
  color: var(--primary);
  font-size: 12px;
}
.account-actions {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.sidebar-action {
  justify-content: flex-start;
  width: 100%;
  min-height: 36px;
  padding: 7px 8px;
  border-color: transparent;
  background: transparent;
  color: var(--gray-600);
  font-size: 13px;
}
.sidebar-action:hover:not(:disabled) {
  background: var(--gray-50);
  color: var(--gray-900);
}
.logout-action:hover:not(:disabled) {
  background: var(--danger-soft);
  color: var(--danger);
}

/* 侧边栏预留 260px，业务页自己的 1180px .container 不变。 */
.app-shell-main {
  min-width: 0;
  padding: 22px 22px 22px 262px;
}
.app-shell-main :deep(.container) {
  margin-left: auto;
  margin-right: auto;
}

</style>
