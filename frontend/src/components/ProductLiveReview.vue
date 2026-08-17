<template>
  <div class="review-card">
    <div class="card-head">
      <h3><Icon name="chart" size="15" class="head-icon" /> 直播复盘</h3>
      <button class="primary-btn" :disabled="generating" @click="generate">
        {{ generating ? "生成中..." : "生成直播复盘" }}
      </button>
    </div>

    <div v-if="!productId" class="hint">选择商品后可生成直播复盘。</div>
    <template v-else>
      <div class="result-box">
        <div v-if="generating" class="hint">AI 正在生成复盘...</div>
        <div v-else-if="generateError" class="hint hint-error">生成失败，请稍后重试。</div>
        <div v-else-if="!record" class="hint">选择商品后可生成直播复盘。</div>
        <template v-else>
          <div class="review-meta">
            <b>{{ statusText(record) }}</b>
            <span class="muted">{{ createdText(record) }}</span>
          </div>
          <div v-if="record.status !== 'success' && record.error_message" class="muted review-warning">
            {{ record.error_message }}
          </div>
          <div class="review-content">{{ record.content }}</div>
        </template>
      </div>

      <div class="history-head">历史复盘</div>
      <div class="history-list">
        <div v-if="historyLoading" class="hint">加载中…</div>
        <div v-else-if="historyError" class="hint hint-error">历史复盘加载失败。</div>
        <div v-else-if="!history.length" class="hint">暂无复盘记录。</div>
        <div v-for="item in history" :key="item.id" class="row-item">
          <div class="history-info">
            <b>{{ statusText(item) }}</b>
            <div class="muted">{{ createdText(item) }}</div>
          </div>
          <button class="light-btn" @click="viewHistory(item.id)">查看</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
// 阶段 4.7：商品直播复盘（与旧页面文案一致）：
// POST /products/{id}/live-reviews 生成、GET /products/{id}/live-reviews 历史列表、
// GET /live-reviews/{id} 查看历史复盘。
import { ref, watch } from "vue";
import { apiGet, apiPost } from "../api/client";
import Icon from "./Icon.vue";

const props = defineProps({
  productId: { type: Number, default: null },
});

const generating = ref(false);
const generateError = ref(false);
const record = ref(null);

const historyLoading = ref(false);
const historyError = ref(false);
const history = ref([]);

function statusText(r) {
  if (r.status === "fallback") return "本地兜底";
  if (r.status === "failed") return "生成失败";
  return "生成成功";
}

function createdText(r) {
  return r.created_at ? new Date(r.created_at).toLocaleString() : "";
}

async function generate() {
  if (!props.productId) {
    alert("请先选择商品");
    return;
  }
  generating.value = true;
  generateError.value = false;
  try {
    const data = await apiPost(`/products/${props.productId}/live-reviews`);
    record.value = data;
    await loadHistory();
  } catch (e) {
    generateError.value = true;
    record.value = null;
  } finally {
    generating.value = false;
  }
}

async function loadHistory() {
  if (!props.productId) return;
  historyLoading.value = true;
  historyError.value = false;
  try {
    history.value = await apiGet(`/products/${props.productId}/live-reviews`);
  } catch (e) {
    historyError.value = true;
    history.value = [];
  } finally {
    historyLoading.value = false;
  }
}

async function viewHistory(id) {
  try {
    const data = await apiGet(`/live-reviews/${id}`);
    record.value = data;
  } catch (e) {
    // 忽略，保持原展示
  }
}

// 切换商品时重置复盘状态（与旧页面一致）
watch(
  () => props.productId,
  (id) => {
    record.value = null;
    generateError.value = false;
    history.value = [];
    if (id) loadHistory();
  },
  { immediate: true }
);
</script>

<style scoped>
.review-card .empty {
  padding: 16px;
}
.review-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.review-meta b {
  font-size: 13px;
}
.review-warning {
  margin-bottom: 8px;
}
.review-content {
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-all;
}
.history-head {
  font-weight: 700;
  font-size: 13px;
  margin: 12px 0 6px;
}
.history-info b {
  font-size: 13px;
}
</style>
