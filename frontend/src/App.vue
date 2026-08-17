<template>
  <div v-if="!session.loaded" class="boot-hint">加载中…</div>
  <LoginView v-else-if="!session.user" />
  <AppShell v-else :view="view" :is-admin="isAdmin" @navigate="view = $event">
    <OperationsDashboardView v-if="view === 'dashboard'" @navigate="view = $event" />
    <HomeView v-else-if="view === 'about'" />
    <MaterialsView v-else-if="view === 'materials'" />
    <ProductKnowledgeView v-else-if="view === 'products'" />
    <CommentAssistantView v-else-if="view === 'comments'" />
    <UserManagementView v-else />
  </AppShell>
  <Feedback />
</template>

<script setup>
// V6 阶段 2：会话状态门控——加载中 / 登录页 / 主应用。
// 主导航已移入 AppShell（view + navigate 由 props/emit 传递）；轻量视图切换，不引入 vue-router。
import { ref, computed, onMounted } from "vue";
import { session, loadSession } from "./state/session";
import AppShell from "./components/AppShell.vue";
import Feedback from "./components/Feedback.vue";
import LoginView from "./views/LoginView.vue";
import HomeView from "./views/HomeView.vue";
import MaterialsView from "./views/MaterialsView.vue";
import ProductKnowledgeView from "./views/ProductKnowledgeView.vue";
import CommentAssistantView from "./views/CommentAssistantView.vue";
import OperationsDashboardView from "./views/OperationsDashboardView.vue";
import UserManagementView from "./views/UserManagementView.vue";

const view = ref("dashboard");

// 仅管理员显示「用户管理」入口（与旧页面 adminNav 行为一致）
const isAdmin = computed(() => session.user && session.user.role === "admin");

onMounted(loadSession);
</script>

<style scoped>
.boot-hint {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--gray-400);
  font-size: 14px;
}
</style>
