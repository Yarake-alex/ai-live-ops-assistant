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
          <AiResultContent :content="record.content" />
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
// V6：生成状态按 productId 保存到模块级 generationTasks，
// 切换 tab 卸载组件后仍能恢复「生成中」，后台完成后同步结果并刷新历史。
import { ref, watch } from "vue";
import { apiGet, apiPost } from "../api/client";
import { toast } from "../state/feedback";
import { getGeneration, startGeneration, finishGeneration } from "../state/generationTasks";
import Icon from "./Icon.vue";
import AiResultContent from "./AiResultContent.vue";

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
    toast("请先选择商品", "error");
    return;
  }
  // 生成中禁止重复发起（按钮已禁用，此处再兜底一次）
  if (generating.value || getGeneration("liveReview", props.productId)?.pending) return;
  generating.value = true;
  generateError.value = false;
  startGeneration("liveReview", props.productId);
  try {
    const data = await apiPost(`/products/${props.productId}/live-reviews`);
    record.value = data;
    // 完成状态写入模块级任务（由任务 watcher 统一刷新历史）
    finishGeneration("liveReview", props.productId, { result: data });
  } catch (e) {
    generateError.value = true;
    record.value = null;
    finishGeneration("liveReview", props.productId, { error: true });
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
    generating.value = false;
    record.value = null;
    generateError.value = false;
    history.value = [];
    if (id) loadHistory();
  },
  { immediate: true }
);

// 生成任务状态同步（跨 tab 切换保持，按 productId 隔离）：
// 挂载时恢复「生成中」或已完成结果；后台请求完成后同步 UI 并刷新历史。
watch(
  () => getGeneration("liveReview", props.productId),
  (task) => {
    if (!task) return;
    if (task.pending) {
      if (!generating.value) generating.value = true;
      return;
    }
    generating.value = false;
    if (task.error) {
      generateError.value = true;
      record.value = null;
    } else if (task.result) {
      generateError.value = false;
      record.value = task.result;
      loadHistory();
    }
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
.history-head {
  font-weight: 700;
  font-size: 13px;
  margin: 12px 0 6px;
}
.history-info b {
  font-size: 13px;
}
</style>
