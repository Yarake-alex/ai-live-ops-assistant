<template>
  <div class="insights-card">
    <div class="card-head">
      <h3>❓ 问题洞察</h3>
      <button class="light-btn" :disabled="loading" @click="load">刷新</button>
    </div>
    <div v-if="!productId" class="hint">选择商品后展示该商品的问题洞察。</div>
    <div v-else-if="loading" class="hint">加载中…</div>
    <div v-else-if="error" class="hint">问题洞察暂不可用，不影响其他功能。</div>
    <div v-else-if="isEmpty" class="hint">暂无问题记录，开始提问后会在这里沉淀高频问题。</div>
    <template v-else>
      <!-- 高频问题 Top 5 -->
      <div v-if="top.length" class="section">
        <div class="section-title">🔥 高频问题</div>
        <div v-for="t in top" :key="t.question" class="row">
          <span class="row-text">{{ t.question }}</span>
          <span class="row-tags">
            <span class="tag">{{ categoryLabel(t.category) }}</span>
            <span class="muted">{{ t.count }} 次</span>
          </span>
        </div>
      </div>

      <!-- 分类统计（只显示 count > 0） -->
      <div v-if="activeCounts.length" class="section">
        <div class="section-title">📊 分类统计</div>
        <div class="count-tags">
          <span v-for="c in activeCounts" :key="c.category" class="tag">
            {{ c.label }} <b>{{ c.count }}</b>
          </span>
        </div>
      </div>

      <!-- 未覆盖问题 -->
      <div v-if="unanswered.length" class="section">
        <div class="section-title">⚠️ 未覆盖问题</div>
        <div v-for="u in unanswered" :key="u.question" class="row">
          <span class="row-text">{{ u.question }}</span>
          <span class="row-tags">
            <span class="tag">{{ categoryLabel(u.category) }}</span>
            <span class="muted">{{ u.count }} 次 · 建议补充资料</span>
          </span>
        </div>
      </div>

      <!-- 最近问题（最多 5 条） -->
      <div v-if="recent.length" class="section">
        <div class="section-title">🕒 最近问题</div>
        <div v-for="r in recent" :key="r.question" class="row">
          <span class="row-text">{{ r.question }}</span>
          <span class="row-tags">
            <span class="tag">{{ categoryLabel(r.category) }}</span>
            <span :class="r.was_answered ? 'status-ok' : 'tag'">
              {{ r.was_answered ? "已回答" : "未覆盖" }}
            </span>
          </span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
// 阶段 4.4：商品问题洞察（与旧页面文案一致）：
// GET /products/{id}/question-insights →
// top_questions / category_counts / recent_questions / unanswered_questions。
import { ref, computed, watch } from "vue";
import { apiGet } from "../api/client";

const props = defineProps({
  productId: { type: Number, default: null },
});

const CATEGORY_LABELS = {
  price: "价格",
  stock: "库存",
  promotion: "优惠",
  audience: "适用人群",
  selling_points: "卖点",
  usage: "使用方法",
  after_sales: "售后",
  risk: "风险边界",
  other: "其他",
};

const loading = ref(false);
const error = ref(false);
const top = ref([]);
const counts = ref([]);
const recent = ref([]);
const unanswered = ref([]);

const activeCounts = computed(() => counts.value.filter((c) => c.count > 0));
const isEmpty = computed(
  () => !top.value.length && !activeCounts.value.length && !recent.value.length
);

function categoryLabel(category) {
  return CATEGORY_LABELS[category] || "其他";
}

async function load() {
  if (!props.productId) return;
  loading.value = true;
  error.value = false;
  try {
    const data = await apiGet(`/products/${props.productId}/question-insights`);
    top.value = data.top_questions || [];
    counts.value = data.category_counts || [];
    recent.value = (data.recent_questions || []).slice(0, 5);
    unanswered.value = data.unanswered_questions || [];
  } catch (e) {
    error.value = true;
    top.value = [];
    counts.value = [];
    recent.value = [];
    unanswered.value = [];
  } finally {
    loading.value = false;
  }
}

watch(() => props.productId, load, { immediate: true });
</script>

<style scoped>
.insights-card {
  margin-top: 12px;
}
.section {
  margin-bottom: 10px;
}
.section-title {
  font-weight: 700;
  font-size: 13px;
  margin: 10px 0 6px;
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  padding: 4px 0;
}
.row-text {
  font-size: 13px;
  min-width: 0;
  word-break: break-all;
  flex: 1;
}
.row-tags {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-shrink: 0;
}
.count-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
</style>
