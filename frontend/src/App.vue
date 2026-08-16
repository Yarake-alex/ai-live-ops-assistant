<template>
  <div v-if="!session.loaded" class="boot-hint">加载中…</div>
  <LoginView v-else-if="!session.user" />
  <AppShell v-else>
    <nav class="page-nav">
      <button :class="{ active: view === 'dashboard' }" @click="view = 'dashboard'">运营工作台</button>
      <button :class="{ active: view === 'products' }" @click="view = 'products'">商品资料</button>
      <button :class="{ active: view === 'materials' }" @click="view = 'materials'">直播素材库</button>
      <button :class="{ active: view === 'comments' }" @click="view = 'comments'">评论助手</button>
      <button :class="{ active: view === 'users' }" @click="view = 'users'">用户管理</button>
      <button :class="{ active: view === 'home' }" @click="view = 'home'">骨架页</button>
    </nav>
    <OperationsDashboardView v-if="view === 'dashboard'" @navigate="view = $event" />
    <HomeView v-else-if="view === 'home'" />
    <MaterialsView v-else-if="view === 'materials'" />
    <ProductKnowledgeView v-else-if="view === 'products'" />
    <CommentAssistantView v-else-if="view === 'comments'" />
    <UserManagementView v-else />
  </AppShell>
</template>

<script setup>
// 阶段 5.6：会话状态门控——加载中 / 登录页 / 主应用。
// 登录成功或 401 后会话状态自动切换；轻量视图切换，不引入 vue-router。
import { ref, onMounted } from "vue";
import { session, loadSession } from "./state/session";
import AppShell from "./components/AppShell.vue";
import LoginView from "./views/LoginView.vue";
import HomeView from "./views/HomeView.vue";
import MaterialsView from "./views/MaterialsView.vue";
import ProductKnowledgeView from "./views/ProductKnowledgeView.vue";
import CommentAssistantView from "./views/CommentAssistantView.vue";
import OperationsDashboardView from "./views/OperationsDashboardView.vue";
import UserManagementView from "./views/UserManagementView.vue";

const view = ref("dashboard");

onMounted(loadSession);
</script>

<style scoped>
.boot-hint {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  font-size: 14px;
}
.page-nav {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding: 12px 24px;
  border-bottom: 1px solid #e5e7eb;
}
.page-nav button {
  padding: 5px 14px;
  font-size: 13px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
  color: #555;
  cursor: pointer;
}
.page-nav button.active {
  background: #eef2ff;
  border-color: #c7d2fe;
  color: #3730a3;
}
</style>
