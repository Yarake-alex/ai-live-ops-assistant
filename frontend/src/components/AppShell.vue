<template>
  <div class="app-shell">
    <!-- 顶栏：左产品名，右用户信息 + 修改密码 / 退出登录 -->
    <header class="topbar">
      <div class="topbar-inner shell-inner">
        <div class="brand">
          <span class="brand-mark">播</span>
          <h1 class="brand-title">AI 直播运营助手</h1>
          <span class="brand-sub">直播运营工作台</span>
        </div>
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
      </div>
    </header>

    <!-- 主导航：稳定导航条，当前模块蓝色高亮 + 底部指示条 -->
    <nav class="main-nav">
      <div class="main-nav-inner shell-inner">
        <button
          v-for="item in navItems"
          :key="item.key"
          :class="{ active: view === item.key }"
          @click="$emit('navigate', item.key)"
        >
          {{ item.label }}
        </button>
      </div>
    </nav>

    <main class="app-shell-main">
      <slot />
    </main>

    <ChangePasswordModal v-if="cpVisible" @close="cpVisible = false" />
  </div>
</template>

<script setup>
// V6 阶段 2：正式后台壳——顶栏（产品名/用户/修改密码/退出登录）+ 主导航条。
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

/* ── 顶栏 ── */
.topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  background: #fff;
  border-bottom: 1px solid var(--panel-border);
}
.topbar-inner {
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.brand {
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
  font-size: 12px;
  color: var(--gray-400);
  border-left: 1px solid var(--gray-200);
  padding-left: 8px;
  white-space: nowrap;
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
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

/* ── 主导航 ── */
.main-nav {
  position: sticky;
  top: 52px;
  z-index: 29;
  background: #fff;
  border-bottom: 1px solid var(--panel-border);
}
.main-nav-inner {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.main-nav button {
  border: none;
  border-radius: 0;
  background: transparent;
  color: var(--gray-600);
  padding: 11px 14px;
  font-size: 14px;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
.main-nav button:hover:not(:disabled) {
  background: var(--gray-50);
  color: var(--gray-900);
}
.main-nav button.active {
  /* 选中态：2px 蓝色底边 + 深色文字，不只依赖颜色 */
  color: var(--gray-900);
  font-weight: 600;
  border-bottom-color: var(--primary);
}

.app-shell-main {
  flex: 1;
}

/* ── 窄屏顶栏：降级为图标按钮 + 隐藏次要品牌信息，防止溢出 ── */
@media (max-width: 480px) {
  .brand-sub {
    display: none;
  }
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
@media (max-width: 360px) {
  .brand-title {
    display: none;
  }
}
</style>
