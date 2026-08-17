<template>
  <div class="prep-summary" aria-label="商品运营状态摘要">
    <div class="prep-item">
      <span class="prep-value">{{ score === null ? "—" : score + "%" }}</span>
      <span class="prep-label">资料完整度</span>
    </div>
    <div class="prep-item">
      <span class="prep-value">{{ docsCount === null ? "—" : docsCount }}</span>
      <span class="prep-label">资料文档</span>
    </div>
    <div class="prep-item">
      <span class="prep-value">{{ topCount === null ? "—" : topCount }}</span>
      <span class="prep-label">高频问题</span>
    </div>
    <div class="prep-item">
      <span class="prep-value">{{ unansweredCount === null ? "—" : unansweredCount }}</span>
      <span class="prep-label">未覆盖问题</span>
    </div>
  </div>
</template>

<script setup>
// 当前商品工作区头部的轻量状态摘要：完整度、资料文档、高频问题、未覆盖问题。
// 保持既有 Promise.all 请求与统计计算规则，不新增接口或业务逻辑。
import { ref, watch } from "vue";
import { apiGet } from "../api/client";

const props = defineProps({
  productId: { type: Number, default: null },
});
// 把已有的资料文档数同时上报给父工作区，供资料依赖操作的禁用态判断；不新增请求。
const emit = defineEmits(["docs"]);

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
  try {
    const [readiness, docs, insights] = await Promise.all([
      apiGet(`/products/${props.productId}/readiness`),
      apiGet(`/products/${props.productId}/knowledge/documents`),
      apiGet(`/products/${props.productId}/question-insights`),
    ]);
    const c = (readiness.completeness || {}).score;
    score.value = Number.isFinite(c) ? c : 0;
    docsCount.value = (docs || []).length;
    emit("docs", docsCount.value);
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
  }
}

watch(() => props.productId, load, { immediate: true });
</script>

<style scoped>
/* 头部摘要是轻量信息行，不再形成一组独立统计卡。 */
.prep-summary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0;
  border: 1px solid var(--gray-100);
  border-radius: var(--radius-sm);
  background: var(--gray-50);
}
.prep-item {
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  padding: 7px 10px;
  white-space: nowrap;
}
.prep-item + .prep-item {
  border-left: 1px solid var(--gray-200);
}
.prep-value {
  font-size: 14px;
  font-weight: 700;
  color: var(--gray-900);
}
.prep-label {
  font-size: 13px;
  color: var(--gray-500);
}
@media (max-width: 768px) {
  .prep-summary {
    width: 100%;
  }
  .prep-item {
    flex: 1 1 50%;
  }
  .prep-item:nth-child(odd) {
    border-left: none;
  }
  .prep-item:nth-child(n + 3) {
    border-top: 1px solid var(--gray-200);
  }
}
@media (max-width: 390px) {
  .prep-item {
    flex-basis: 100%;
  }
  .prep-item + .prep-item {
    border-left: none;
    border-top: 1px solid var(--gray-200);
  }
}
</style>
