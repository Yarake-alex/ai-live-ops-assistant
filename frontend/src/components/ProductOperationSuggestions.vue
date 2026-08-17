<template>
  <div class="ops-card">
    <div class="card-head">
      <h3><Icon name="bulb" size="15" class="head-icon" /> 运营建议</h3>
    </div>
    <p class="ops-desc">运营建议会根据未覆盖问题、高频重复问题和资料缺口汇总生成；如果资料已能回答相关问题，建议可能不会变化。</p>
    <div v-if="!productId" class="hint">选择商品后展示该商品的运营建议。</div>
    <div v-else-if="loading" class="hint">加载中…</div>
    <div v-else-if="error" class="hint">运营建议暂不可用，不影响其他功能</div>
    <template v-else>
      <!-- 汇总三格（与旧页面一致） -->
      <div class="summary-row">
        <div class="summary-item">
          <div class="summary-value">{{ summary.total ?? 0 }}</div>
          <div class="summary-label">建议总数</div>
        </div>
        <div class="summary-item">
          <div class="summary-value" style="color: #ef4444">{{ summary.high_priority ?? 0 }}</div>
          <div class="summary-label">高优先级</div>
        </div>
        <div class="summary-item">
          <div class="summary-value" :style="{ color: summary.needs_material_update ? '#ef4444' : '#10b981' }">
            {{ summary.needs_material_update ? "建议补资料" : "暂不需要补资料" }}
          </div>
          <div class="summary-label">资料状态</div>
        </div>
      </div>

      <div v-if="!list.length" class="hint">
        暂无运营建议，表示暂未发现明显资料缺口或话术优化点。积累更多商品问题后，这里会提示该补充哪些资料和话术。
      </div>
      <div v-else class="suggestion-list">
        <div v-for="(s, i) in list" :key="i" class="suggestion-item">
          <div class="suggestion-top">
            <span class="tag">{{ typeLabel(s.type) }}</span>
            <span class="tag" :style="priorityStyle(s.priority)">{{ priorityLabel(s.priority) }}</span>
            <b class="suggestion-title">{{ s.title || "" }}</b>
          </div>
          <div class="suggestion-detail">{{ s.detail || "" }}</div>
          <div v-if="sourceQuestions(s).length" class="suggestion-questions">
            来源问题：{{ sourceQuestions(s).join("、") }}
          </div>
          <div class="suggestion-action">
            <span class="tag">{{ s.action_label || "" }}</span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
// 阶段 4.5：商品运营建议（与旧页面文案一致）：
// GET /products/{id}/ops-suggestions → {summary, suggestions}。
// V6：增加聚合生成说明（解释建议不随每次提问实时变化）；
// 建议列表限高内部滚动；生成逻辑与接口不变。
import { ref, watch } from "vue";
import { apiGet } from "../api/client";
import Icon from "./Icon.vue";

const props = defineProps({
  productId: { type: Number, default: null },
});

const TYPE_LABELS = {
  material_gap: "资料补齐",
  faq_candidate: "FAQ 建议",
  script_focus: "话术强化",
  risk_reminder: "风险提醒",
};
const PRIORITY_LABELS = { high: "高", medium: "中", low: "低" };
const PRIORITY_STYLES = {
  high: "background:#fef2f2;color:#991b1b",
  medium: "background:#fffbeb;color:#92400e",
  low: "background:#f0f9ff;color:#075985",
};

const loading = ref(false);
const error = ref(false);
const summary = ref({});
const list = ref([]);

function typeLabel(type) {
  return TYPE_LABELS[type] || "建议";
}
function priorityLabel(priority) {
  return PRIORITY_LABELS[priority] || "低";
}
function priorityStyle(priority) {
  return PRIORITY_STYLES[priority] || PRIORITY_STYLES.low;
}
function sourceQuestions(s) {
  return (s.source_questions || []).slice(0, 3);
}

async function load() {
  if (!props.productId) return;
  loading.value = true;
  error.value = false;
  try {
    const data = await apiGet(`/products/${props.productId}/ops-suggestions`);
    summary.value = data.summary || {};
    list.value = data.suggestions || [];
  } catch (e) {
    error.value = true;
    summary.value = {};
    list.value = [];
  } finally {
    loading.value = false;
  }
}

watch(() => props.productId, load, { immediate: true });
</script>

<style scoped>
.ops-card .empty {
  padding: 24px 16px;
}
/* 聚合生成说明：弱文本，不喧宾夺主 */
.ops-desc {
  margin: -2px 0 10px;
  color: var(--gray-500);
  font-size: var(--text-xs);
  line-height: 1.7;
}
.summary-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.summary-item {
  border: 1px solid var(--gray-100);
  border-radius: var(--radius-sm);
  padding: 8px 14px;
  text-align: center;
  background: var(--gray-50);
}
.summary-value {
  font-size: 16px;
  font-weight: 600;
}
.summary-label {
  color: var(--gray-500);
  font-size: 11px;
}
/* 建议列表：限高内部滚动，浅背景 + 轻边框给出清楚边界 */
.suggestion-list {
  max-height: 480px;
  overflow-y: auto;
  background: var(--gray-50);
  border: 1px solid var(--gray-100);
  border-radius: var(--radius-sm);
  padding: 10px;
}
.suggestion-item {
  display: block;
  border: 1px solid var(--gray-100);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  margin-bottom: 8px;
  background: #fff;
}
.suggestion-item:last-child {
  margin-bottom: 0;
}
.suggestion-top {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.suggestion-title {
  font-size: 13px;
  min-width: 0;
  word-break: break-all;
}
.suggestion-detail {
  color: var(--gray-500);
  font-size: 12px;
  line-height: 1.7;
  word-break: break-all;
}
.suggestion-questions {
  color: var(--gray-500);
  font-size: 11px;
  margin-top: 4px;
  word-break: break-all;
}
.suggestion-action {
  margin-top: 6px;
}
</style>
