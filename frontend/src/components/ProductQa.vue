<template>
  <div class="qa-card">
    <div class="card-head">
      <h3>💬 资料问答</h3>
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
    <div class="qa-result">
      <div v-if="asking" class="hint">检索资料中...</div>
      <div v-else-if="error" class="hint hint-error">提问失败，请稍后重试。</div>
      <div v-else-if="!answer" class="hint">基于商品资料的回答会显示在这里。</div>
      <template v-else>
        <div class="answer-text">{{ answer }}</div>
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
    alert("请先选择商品");
    return;
  }
  if (!q) {
    alert("请输入问题");
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
.qa-card {
  margin-top: 12px;
}
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
.qa-result {
  min-height: 60px;
  border: 1px solid var(--gray-100);
  border-radius: var(--radius-sm);
  background: var(--gray-50);
  padding: 10px 12px;
}
.answer-text {
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-all;
}
.answer-sources {
  color: var(--gray-500);
  font-size: 12px;
  margin-top: 8px;
  word-break: break-all;
}
</style>
