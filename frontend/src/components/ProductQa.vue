<template>
  <div class="qa-card">
    <div class="card-head">
      <h3><Icon name="chat" size="15" class="head-icon" /> 资料问答</h3>
    </div>
    <div class="qa-input-row">
      <input
        v-model="question"
        type="text"
        placeholder="向商品资料提问，例如：这款商品怎么介绍卖点？"
        :disabled="asking"
        @keydown.enter="ask"
      />
      <button class="primary-btn" :disabled="asking || !question.trim()" @click="ask">提问</button>
    </div>
    <div class="result-box">
      <div v-if="asking" class="hint">检索资料中...</div>
      <div v-else-if="error" class="hint hint-error">提问失败，请稍后重试。</div>
      <div v-else-if="!answer" class="empty">
        <span class="empty-icon"><Icon name="chat" size="24" /></span>
        <span>基于商品资料的回答会显示在这里。</span>
      </div>
      <template v-else>
        <AiResultContent :content="answer" />
        <div v-if="sources.length" class="answer-sources">
          参考片段：{{ sources.map((s) => `${s.filename}#${s.chunk_index}`).join("、") }}
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
// 阶段 4.3：商品资料问答（本地快答与知识库问答共用同一接口，与旧页面一致）：
// POST /products/{id}/knowledge/ask {question} → {answer, sources}。
// 问题洞察与运营建议的联动刷新留待后续阶段迁移。
import { ref, watch } from "vue";
import { apiPost } from "../api/client";
import { toast } from "../state/feedback";
import Icon from "./Icon.vue";
import AiResultContent from "./AiResultContent.vue";

const props = defineProps({
  productId: { type: Number, default: null },
});

const question = ref("");
const asking = ref(false);
const error = ref(false);
const answer = ref("");
const sources = ref([]);

async function ask() {
  const q = question.value.trim();
  if (!props.productId) {
    toast("请先选择商品", "error");
    return;
  }
  if (!q) {
    toast("请输入问题", "error");
    return;
  }
  if (asking.value) return;

  asking.value = true;
  error.value = false;
  try {
    const data = await apiPost(`/products/${props.productId}/knowledge/ask`, { question: q });
    answer.value = data.answer || "";
    sources.value = data.sources || [];
  } catch (e) {
    error.value = true;
    answer.value = "";
    sources.value = [];
  } finally {
    asking.value = false;
  }
}

// 切换商品时清空问答状态（与旧页面一致）
watch(
  () => props.productId,
  () => {
    question.value = "";
    answer.value = "";
    sources.value = [];
    error.value = false;
  }
);
</script>

<style scoped>
.qa-input-row {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}
.qa-input-row input {
  flex: 1;
  min-width: 0;
}
.qa-input-row .primary-btn {
  flex-shrink: 0;
}
.qa-card .empty {
  padding: 16px;
}
/* 回答结果区限高内部滚动（420-520px 区间），长回答不再拉长页面 */
.qa-card .result-box {
  max-height: 480px;
  overflow-y: auto;
}
.answer-sources {
  color: var(--gray-500);
  font-size: 12px;
  margin-top: 8px;
  word-break: break-all;
  /* 参考片段行限高，超出内部滚动 */
  max-height: 64px;
  overflow-y: auto;
}
</style>
