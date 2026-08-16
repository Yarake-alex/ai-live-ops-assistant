<template>
  <div class="completeness-card">
    <div class="card-head">
      <h3>✅ 资料完整度</h3>
      <button class="light-btn" :disabled="loading" @click="load">刷新</button>
    </div>
    <div v-if="!productId" class="hint">选择商品后可查看资料完整度。</div>
    <div v-else-if="loading" class="hint">加载中…</div>
    <div v-else-if="error" class="hint">完整度暂不可用，不影响其他功能。</div>
    <template v-else>
      <div class="score-row">
        <div class="score-value" :style="{ color }">{{ pct }}%</div>
        <div class="score-bar-wrap">
          <div class="score-bar">
            <div class="score-bar-fill" :style="{ width: pct + '%', background: color }"></div>
          </div>
          <div class="score-label">资料完整度</div>
        </div>
      </div>
      <div v-if="missing.length" class="missing-line"><b>缺失项：</b>{{ missing.join("、") }}</div>
      <div v-if="suggestions.length" class="suggestions">
        <b>下一步建议：</b><br />
        <div v-for="s in suggestions" :key="s">· {{ s }}</div>
      </div>
      <div v-else-if="!missing.length" class="done-line">资料已完善，可以开始准备开播。</div>
    </template>
  </div>
</template>

<script setup>
// 阶段 4.2：商品资料完整度（与旧页面文案/配色一致）：
// GET /products/{id}/readiness → score / missing_items / suggestions。
import { ref, computed, watch } from "vue";
import { apiGet } from "../api/client";

const props = defineProps({
  productId: { type: Number, default: null },
});

const loading = ref(false);
const error = ref(false);
const score = ref(0);
const missing = ref([]);
const suggestions = ref([]);

const pct = computed(() => (Number.isFinite(score.value) ? score.value : 0));
const color = computed(() =>
  pct.value >= 80 ? "#10b981" : pct.value >= 50 ? "#f59e0b" : "#ef4444"
);

async function load() {
  if (!props.productId) return;
  loading.value = true;
  error.value = false;
  try {
    const data = await apiGet(`/products/${props.productId}/readiness`);
    const c = data.completeness || {};
    score.value = c.score ?? 0;
    missing.value = c.missing_items || [];
    suggestions.value = c.suggestions || [];
  } catch (e) {
    error.value = true;
  } finally {
    loading.value = false;
  }
}

watch(() => props.productId, load, { immediate: true });
</script>

<style scoped>
.completeness-card {
  margin-top: 12px;
}
.score-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.score-value {
  font-size: 28px;
  font-weight: 700;
}
.score-bar-wrap {
  flex: 1;
  min-width: 120px;
}
.score-bar {
  height: 8px;
  background: var(--gray-200);
  border-radius: 4px;
  overflow: hidden;
}
.score-bar-fill {
  height: 100%;
  border-radius: 4px;
}
.score-label {
  color: var(--gray-500);
  font-size: 11px;
  margin-top: 4px;
}
.missing-line {
  font-size: 13px;
  margin-bottom: 6px;
  word-break: break-all;
}
.suggestions {
  color: var(--gray-500);
  font-size: 12px;
  line-height: 1.8;
}
.done-line {
  font-size: 13px;
  color: var(--success);
}
</style>
