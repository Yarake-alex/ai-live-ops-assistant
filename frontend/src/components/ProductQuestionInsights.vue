<template>
  <div class="insights-card">
    <div class="card-head">
      <h3><Icon name="help" size="15" class="head-icon" /> 问题洞察</h3>
    </div>
    <div v-if="!productId" class="hint">选择商品后展示该商品的问题洞察。</div>
    <div v-else-if="loading" class="hint">加载中…</div>
    <div v-else-if="error" class="hint">问题洞察暂不可用，不影响其他功能。</div>
    <div v-else-if="isEmpty" class="hint">暂无问题记录，开始提问后会在这里沉淀高频问题。</div>
    <template v-else>
      <!-- 顺序按运营工作流：最近问题 → 高频问题 → 分类统计 → 未覆盖问题；
           内容区限高内部滚动，各列表最多直接展示 5 条。 -->
      <div class="insights-body">
        <!-- 最近问题（最多 5 条）：运营最先关心最近观众在问什么 -->
        <div v-if="recent.length" class="section">
          <div class="section-title">最近问题</div>
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

        <!-- 高频问题（最多 5 条）：看重复出现的问题 -->
        <div v-if="top.length" class="section">
          <div class="section-title">高频问题</div>
          <div v-for="t in top.slice(0, 5)" :key="t.question" class="row">
            <span class="row-text">{{ t.question }}</span>
            <span class="row-tags">
              <span class="tag">{{ categoryLabel(t.category) }}</span>
              <span class="muted">{{ t.count }} 次</span>
            </span>
          </div>
        </div>

        <!-- 分类统计（只显示 count > 0）：紧凑概览 -->
        <div v-if="activeCounts.length" class="section">
          <div class="section-title">分类统计</div>
          <div class="count-tags">
            <span v-for="c in activeCounts" :key="c.category" class="tag">
              {{ c.label }} <b>{{ c.count }}</b>
            </span>
          </div>
        </div>

        <!-- 未覆盖问题（最多 5 条） -->
        <div v-if="unanswered.length" class="section">
          <div class="section-title">未覆盖问题</div>
          <div v-for="u in unanswered.slice(0, 5)" :key="u.question" class="row">
            <span class="row-text">{{ u.question }}</span>
            <span class="row-tags">
              <span class="tag">{{ categoryLabel(u.category) }}</span>
              <span class="muted">{{ u.count }} 次 · 建议补充资料</span>
            </span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
// 阶段 4.4：商品问题洞察（与旧页面文案一致）：
// GET /products/{id}/question-insights →
// top_questions / category_counts / recent_questions / unanswered_questions。
// V6：展示顺序调整为运营工作流（最近问题 → 高频问题 → 分类统计 → 未覆盖问题），
// 各列表最多直接展示 5 条；接口与返回结构不变。
// V6 联动：商品资料问答成功后父组件通过 key 重挂载本组件以刷新洞察。
import { ref, computed, watch } from "vue";
import { apiGet } from "../api/client";
import Icon from "./Icon.vue";

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
.insights-card .empty {
  padding: 24px 16px;
}
/* 卡片纵向弹性布局：内容区占据剩余高度并内部滚动，
   与左侧资料问答卡片等高对齐（桌面端由父组件固定 560px 卡高） */
.insights-card {
  display: flex;
  flex-direction: column;
}
/* 洞察内容区：浅背景 + 轻边框给出清楚边界 */
.insights-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  background: var(--gray-50);
  border: 1px solid var(--gray-100);
  border-radius: var(--radius-sm);
  padding: 4px 10px;
}
/* 窄屏上下堆叠时无固定卡高，用 max-height 兜底 */
@media (max-width: 900px) {
  .insights-body {
    max-height: 420px;
  }
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
