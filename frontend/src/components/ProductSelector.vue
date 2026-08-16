<template>
  <div class="product-selector">
    <div class="selector-head">
      <span class="selector-title">商品列表</span>
      <span class="selector-count">{{ total }}</span>
    </div>
    <input
      v-model="q"
      type="text"
      placeholder="搜索商品名称、卖点、人群、痛点、备注…"
      @input="onSearchInput"
      @keydown.enter="searchNow"
    />
    <div class="filter-row">
      <select v-model="liveStatus" @change="searchNow">
        <option value="">直播状态（全部）</option>
        <option value="未上播">未上播</option>
        <option value="直播中">直播中</option>
        <option value="已下播">已下播</option>
      </select>
      <button class="reset-btn" @click="reset">重置</button>
    </div>

    <div class="product-list">
      <div v-if="loading" class="list-hint">加载中…</div>
      <div v-else-if="error" class="list-hint list-error">商品列表加载失败。</div>
      <div v-else-if="!products.length" class="list-hint">暂无商品，请先新增或导入商品。</div>
      <div
        v-for="p in products"
        :key="p.id"
        class="list-item"
        :class="{ selected: p.id === selectedId }"
        @click="$emit('select', p.id)"
      >
        <div class="item-top">
          <b>{{ p.name }}</b>
          <span class="status-tag">{{ p.live_status || "未上播" }}</span>
        </div>
        <div class="muted">💰 ¥{{ p.price }} · 库存 {{ p.stock }}</div>
        <div class="muted item-points">{{ points(p) }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 阶段 4.1：商品选择器（与旧页面交互一致）：
// GET /products/search?q=&live_status=&page=1&page_size=100，搜索 400ms 防抖、
// Enter 立即搜索、状态筛选、重置、选中高亮、列表内滚。
import { ref, onMounted } from "vue";
import { apiGet } from "../api/client";

defineProps({
  selectedId: { type: Number, default: null },
});
const emit = defineEmits(["select"]);

const q = ref("");
const liveStatus = ref("");
const products = ref([]);
const total = ref(0);
const loading = ref(false);
const error = ref(false);

let timer = null;

function points(p) {
  const s = (p.selling_points || "").slice(0, 40);
  return s ? `${s}…` : "";
}

function buildParams() {
  const params = new URLSearchParams();
  if (q.value.trim()) params.set("q", q.value.trim());
  if (liveStatus.value) params.set("live_status", liveStatus.value);
  params.set("page", "1");
  params.set("page_size", "100");
  return params;
}

async function loadProducts() {
  loading.value = true;
  error.value = false;
  try {
    const data = await apiGet(`/products/search?${buildParams().toString()}`);
    products.value = data.items || [];
    total.value = data.total || 0;
  } catch (e) {
    error.value = true;
    products.value = [];
  } finally {
    loading.value = false;
  }
}

function onSearchInput() {
  if (timer) clearTimeout(timer);
  timer = setTimeout(loadProducts, 400);
}

function searchNow() {
  if (timer) clearTimeout(timer);
  loadProducts();
}

function reset() {
  q.value = "";
  liveStatus.value = "";
  searchNow();
}

onMounted(loadProducts);
</script>

<style scoped>
.product-selector {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}
.selector-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.selector-title {
  font-weight: 700;
  font-size: 15px;
}
.selector-count {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #777;
}
.product-selector input {
  font-size: 13px;
}
.filter-row {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}
.filter-row select {
  flex: 1;
  font-size: 11px;
  padding: 6px 4px;
}
.reset-btn {
  font-size: 11px;
  padding: 4px 8px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
  color: #555;
  cursor: pointer;
}
.product-list {
  max-height: 52vh;
  overflow-y: auto;
}
.list-hint {
  padding: 32px 12px;
  text-align: center;
  color: #999;
  font-size: 13px;
}
.list-error {
  color: #b91c1c;
}
.list-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid transparent;
}
.list-item:hover {
  background: #f9fafb;
}
.list-item.selected {
  background: #eef2ff;
  border-color: #c7d2fe;
}
.item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.item-top b {
  min-width: 0;
  word-break: break-all;
}
.status-tag {
  flex-shrink: 0;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #555;
}
.muted {
  color: #777;
  font-size: 12px;
  margin-top: 2px;
}
.item-points {
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
