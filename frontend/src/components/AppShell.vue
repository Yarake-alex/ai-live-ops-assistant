<template>
  <div class="app-shell">
    <!-- 单一顶栏（60px）：品牌 + 主导航 + 用户区，减少重复白色横条 -->
    <header class="topbar shell-inner">
      <div class="brand">
        <span class="brand-mark">播</span>
        <h1 class="brand-title">AI 直播运营助手</h1>
        <span class="brand-sub">直播运营工作台</span>
      </div>
      <nav class="main-nav" aria-label="主导航">
        <button
          v-for="item in navItems"
          :key="item.key"
          :class="{ active: view === item.key }"
          @click="$emit('navigate', item.key)"
        >
          {{ item.label }}
        </button>
      </nav>
      <div class="topbar-right">
        <span v-if="session.user" class="user-chip">
          <span class="user-avatar">{{ (session.user.username || "?").slice(0, 1).toUpperCase() }}</span>
          <span class="user-name">{{ session.user.username }}</span>
          <span v-if="isAdmin" class="tag tag-primary">管理员</span>
        </span>
        <template v-if="session.user">
          <button class="header-btn" aria-label="修改密码" @click="cpVisible = true">
            <Icon name="lock" size="14" /><span>修改密码</span>
          </button>
          <button class="header-btn logout-btn" aria-label="退出登录" @click="onLogout">
            <Icon name="logout" size="14" /><span>退出登录</span>
          </button>
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
// V6 阶段 2：正式后台壳。V6 IA 收紧：品牌/主导航/用户区收敛为单一 60px 顶栏
// （56-64 区间），主导航内嵌（窄屏可横向滚动），导航与登录态行为不变。
// 导航项由 App.vue 传入当前 view 并监听 navigate（不引入 vue-router）。
import { computed, ref } from "vue";
import { session, logout } from "../state/session";
import ChangePasswordModal from "./ChangePasswordModal.vue";
import Icon from "./Icon.vue";

const props = defineProps({
  view: { type: String, default: "dashboard" },
  isAdmin: { type: Boolean, default: false },
});
defineEmits(["navigate"]);

const cpVisible = ref(false);

const navItems = computed(() => {
  const items = [
    { key: "dashboard", label: "运营工作台" },
    { key: "products", label: "商品资料" },
    { key: "materials", label: "直播素材库" },
    { key: "comments", label: "评论助手" },
  ];
  if (props.isAdmin) items.push({ key: "users", label: "用户管理" });
  items.push({ key: "about", label: "关于" });
  return items;
});

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

/* ── 单一顶栏 ── */
.topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  /* sticky 在列向 flex 中不受 cross-axis stretch 约束，显式占满可用宽度 */
  width: 100%;
  background: #fff;
  border-bottom: 1px solid var(--panel-border);
  height: 60px;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 16px;
}
.brand {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.brand-mark {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--primary);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  border-radius: 6px;
}
.brand-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--gray-900);
  white-space: nowrap;
}
.brand-sub {
  font-size: 13px;
  color: var(--gray-400);
  border-left: 1px solid var(--gray-200);
  padding-left: 8px;
  white-space: nowrap;
}

/* 主导航：单行内嵌，窄屏可横向滚动；选中态深色文字 + 2px 蓝色底边 */
.main-nav {
  flex: 1;
  min-width: 0;
  height: 100%;
  display: flex;
  justify-content: center;
  gap: 2px;
  overflow-x: auto;
  scrollbar-width: none;
}
.main-nav::-webkit-scrollbar {
  display: none;
}
.main-nav button {
  border: none;
  border-radius: 0;
  background: transparent;
  color: var(--gray-600);
  height: 100%;
  padding: 0 14px;
  font-size: 14px;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  white-space: nowrap;
}
.main-nav button:hover:not(:disabled) {
  background: var(--gray-50);
  color: var(--gray-900);
}
.main-nav button.active {
  color: var(--gray-900);
  font-weight: 600;
  border-bottom-color: var(--primary);
}

.topbar-right {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.user-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--gray-700);
}
.user-avatar {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-soft);
  color: var(--primary);
  font-size: 12px;
  font-weight: 700;
  border-radius: 50%;
}
.user-name {
  font-weight: 600;
}
.logout-btn:hover:not(:disabled) {
  color: var(--danger);
  border-color: #fecaca;
  background: var(--danger-soft);
}

.app-shell-main {
  flex: 1;
  min-width: 0;
}

/* ── 窄屏降级：先藏次要品牌信息，再图标化用户操作，导航保持可横向滚动 ── */
@media (max-width: 1024px) {
  .brand-sub {
    display: none;
  }
  .main-nav {
    justify-content: flex-start;
  }
}
@media (max-width: 768px) {
  .brand-title {
    display: none;
  }
  .topbar {
    gap: 10px;
  }
}
@media (max-width: 480px) {
  .user-chip .tag {
    display: none;
  }
  .header-btn span {
    display: none;
  }
  .header-btn {
    padding: 8px 10px;
  }
}
</style>
