<template>
  <div class="qa-card">
    <div class="card-head">
      <h3>💬 资料问答</h3>
    </div>
    <textarea
      v-model="question"
      placeholder="例如：直播间退换货规则是什么？活动赠品怎么说？哪些话不能承诺？"
      :disabled="asking"
      rows="3"
    ></textarea>
    <div class="qa-actions">
      <button class="primary-btn" :disabled="asking || !question.trim()" @click="ask">基于资料回答</button>
    </div>

    <div class="qa-result">
      <div v-if="asking" class="hint">正在检索资料并生成回答...</div>
      <div v-else-if="error" class="hint hint-error">提问失败，请稍后重试。</div>
      <div v-else-if="!answer" class="hint">上传资料后，可以在这里提问。</div>
      <template v-else>
        <div class="answer-text">{{ answer }}</div>

        <!-- 参考资料片段：默认折叠（与旧页面一致） -->
        <div v-if="sources.length" class="source-box">
          <div class="source-head">
            <b>参考资料片段：</b>
            <button class="light-btn" @click="showSources = !showSources">
              {{ showSources ? "隐藏参考资料" : "显示参考资料" }}
            </button>
          </div>
          <div v-if="showSources" class="source-detail">
            <div v-for="(s, index) in sources" :key="index" class="source-item">
              <b>资料 {{ index + 1 }}：</b>{{ s.filename }}，片段 {{ s.chunk_index }}<br />
              <span class="muted">{{ s.content }}...</span>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
// 阶段 5.1：直播素材库资料问答（与旧页面文案一致）：
// POST /rag/ask {question} → {answer, sources}，参考资料片段默认折叠展示。
import { ref } from "vue";
import { apiPost } from "../api/client";

const question = ref("");
const asking = ref(false);
const error = ref(false);
const answer = ref("");
const sources = ref([]);
const showSources = ref(false);

async function ask() {
  const q = question.value.trim();
  if (!q) {
    alert("请输入问题");
    return;
  }
  if (asking.value) return;

  asking.value = true;
  error.value = false;
  try {
    const data = await apiPost("/rag/ask", { question: q });
    answer.value = data.answer || "";
    sources.value = data.sources || [];
    showSources.value = false;
  } catch (e) {
    error.value = true;
    answer.value = "";
    sources.value = [];
  } finally {
    asking.value = false;
  }
}
</script>

<style scoped>
.qa-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
  margin-top: 12px;
}
.card-head {
  margin-bottom: 10px;
}
.card-head h3 {
  margin: 0;
  font-size: 15px;
}
textarea {
  width: 100%;
  font-size: 13px;
  min-height: 60px;
}
.qa-actions {
  display: flex;
  justify-content: flex-end;
  margin: 8px 0;
}
.primary-btn {
  padding: 6px 16px;
  font-size: 13px;
  border: none;
  border-radius: 6px;
  background: #16a34a;
  color: #fff;
  cursor: pointer;
}
.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.qa-result {
  border: 1px solid #f3f4f6;
  border-radius: 6px;
  background: #fafafa;
  padding: 10px 12px;
  min-height: 60px;
}
.hint {
  color: #999;
  font-size: 13px;
  padding: 12px 4px;
  text-align: center;
}
.hint-error {
  color: #b91c1c;
}
.answer-text {
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-all;
}
.source-box {
  margin-top: 10px;
  border-top: 1px solid #f3f4f6;
  padding-top: 8px;
}
.source-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.source-head b {
  font-size: 13px;
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
.source-detail {
  margin-top: 8px;
}
.source-item {
  margin-top: 8px;
  font-size: 13px;
  word-break: break-all;
}
.muted {
  color: #777;
  font-size: 12px;
}
</style>
