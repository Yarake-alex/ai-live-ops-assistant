<template>
  <AppShell>
    <nav class="page-nav">
      <button :class="{ active: view === 'home' }" @click="view = 'home'">骨架页</button>
      <button :class="{ active: view === 'materials' }" @click="view = 'materials'">直播素材库</button>
      <button :class="{ active: view === 'products' }" @click="view = 'products'">商品资料</button>
    </nav>
    <HomeView v-if="view === 'home'" />
    <MaterialsView v-else-if="view === 'materials'" />
    <ProductKnowledgeView v-else />
  </AppShell>
</template>

<script setup>
// 迁移初期用轻量视图切换，不引入 vue-router；页面增多后再评估。
import { ref } from "vue";
import AppShell from "./components/AppShell.vue";
import HomeView from "./views/HomeView.vue";
import MaterialsView from "./views/MaterialsView.vue";
import ProductKnowledgeView from "./views/ProductKnowledgeView.vue";

const view = ref("home");
</script>

<style scoped>
.page-nav {
  display: flex;
  gap: 8px;
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
