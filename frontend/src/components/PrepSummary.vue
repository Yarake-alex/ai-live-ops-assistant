<template>
  <div class="prep-card">
    <div class="prep-head">
      <h3>🎯 开播准备概览</h3>
      <button class="light-btn" :disabled="loading" @click="load">刷新</button>
    </div>
    <div class="prep-items">
      <div class="prep-item">
        <div class="prep-value">{{ score === null ? "—" : score + "%" }}</div>
        <div class="prep-label">资料完整度</div>
      </div>
      <div class="prep-item">
        <div class="prep-value">{{ docsCount === null ? "—" : docsCount }}</div>
        <div class="prep-label">资料文档</div>
      </div>
      <div class="prep-item">
        <div class="prep-value">{{ topCount === null ? "—" : topCount }}</div>
        <div class="prep-label">高频问题</div>
      </div>
      <div class="prep-item">
        <div class="prep-value">{{ unansweredCount === null ? "—" : unansweredCount }}</div>
        <div class="prep-label">未覆盖问题</div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 阶段 5.7：开播准备概览条（与旧页面一致）：
// 完整度（readiness.score）、文档数（knowledge/documents 数量）、
// 高频问题（top_questions 计数和）、未覆盖问题（unanswered_questions 计数和）。
import { ref, watch } from "vue";
import { apiGet } from "../api/client";

const props = defineProps({
  productId: { type: Number, default: null },
});

const loading = ref(false);
const score = ref(null);
const docsCount = ref(null);
const topCount = ref(null);
const unansweredCount = ref(null);

async function load() {
  if (!props.productId) {
    score.value = null;
    docsCount.value = null;
    topCount.value = null;
    unansweredCount.value = null;
    return;
  }
  loading.value = true;
  try {
    const [readiness, docs, insights] = await Promise.all([
      apiGet(`/products/${props.productId}/readiness`),
      apiGet(`/products/${props.productId}/knowledge/documents`),
      apiGet(`/products/${props.productId}/question-insights`),
    ]);
    const c = (readiness.completeness || {}).score;
    score.value = Number.isFinite(c) ? c : 0;
    docsCount.value = (docs || []).length;
    topCount.value = (insights.top_questions || []).reduce((a, b) => a + (b.count || 0), 0);
    unansweredCount.value = (insights.unanswered_questions || []).reduce(
      (a, b) => a + (b.count || 0),
      0
    );
  } catch (e) {
    score.value = null;
    docsCount.value = null;
    topCount.value = null;
    unansweredCount.value = null;
  } finally {
    loading.value = false;
  }
}

watch(() => props.productId, load, { immediate: true });
</script>

<style scoped>
.prep-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 14px 16px;
  margin-top: 12px;
}
.prep-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.prep-head h3 {
  margin: 0;
  font-size: 15px;
}
.light-btn {
  font-size: 12px;
  padding: 4px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
  color: #555;
  cursor: pointer;
}
.light-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.prep-items {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.prep-item {
  border: 1px solid #f3f4f6;
  border-radius: 6px;
  padding: 8px 14px;
  text-align: center;
  min-width: 90px;
}
.prep-value {
  font-size: 16px;
  font-weight: 700;
}
.prep-label {
  color: #777;
  font-size: 11px;
}
</style>
