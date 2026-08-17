<template>
  <div class="script-card">
    <div class="card-head">
      <h3><Icon name="mic" size="15" class="head-icon" /> 直播话术</h3>
      <button class="primary-btn" :disabled="generating || !!disableHint" @click="generate">
        {{ generating ? "生成中..." : "生成直播话术" }}
      </button>
    </div>

    <div v-if="disableHint" class="alert alert-info gen-gate">{{ disableHint }}</div>

    <div v-if="!productId" class="hint">选择商品后可用。</div>
    <template v-else>
      <div v-if="statusText" class="status-line">{{ statusText }}</div>

      <div class="result-box">
        <div v-if="generating" class="hint">AI 正在生成直播话术...</div>
        <div v-else-if="generateError" class="hint hint-error">生成失败，请稍后重试。</div>
        <div v-else-if="!script" class="hint">点击“生成直播话术”后，结果会显示在这里。</div>
        <template v-else>
          <div class="script-meta">
            <b>{{ scriptStatusLabel(script) }}</b>
            <span class="muted">{{ createdText(script) }}</span>
          </div>
          <div v-if="script.status === 'fallback' && script.error_message" class="muted fallback-warning">
            AI 暂时不可用，已返回本地兜底话术。
          </div>
          <AiResultContent :content="script.content" />
        </template>
      </div>

      <div class="history-head">历史话术</div>
      <div class="history-list">
        <div v-if="historyLoading" class="hint">加载中…</div>
        <div v-else-if="historyError" class="hint hint-error">历史话术加载失败。</div>
        <div v-else-if="!history.length" class="hint">暂无历史话术。</div>
        <div v-for="item in history" :key="item.id" class="row-item">
          <div class="history-info">
            <b>{{ scriptStatusLabel(item) }}</b>
            <span class="tag">{{ item.provider || "mock" }}</span>
            <div class="muted">{{ createdText(item) }}</div>
          </div>
          <button class="light-btn" @click="viewHistory(item.id)">查看</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
// 阶段 4.6：商品直播话术（与旧页面文案一致）：
// POST /products/{id}/live-scripts 生成、GET /products/{id}/live-scripts 历史列表、
// GET /live-scripts/{id} 查看历史话术。
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
  // 前置条件不足时的解释文案：非空时禁用生成按钮并显示提示（V6 IA 收紧）
  disableHint: { type: String, default: "" },
});

const generating = ref(false);
const generateError = ref(false);
const statusText = ref("");
const script = ref(null);

const historyLoading = ref(false);
const historyError = ref(false);
const history = ref([]);

function scriptStatusLabel(s) {
  if (s.status === "fallback") return "本地兜底";
  if (s.status === "failed") return "生成失败";
  return "生成成功";
}

function createdText(s) {
  return s.created_at ? new Date(s.created_at).toLocaleString() : "";
}

async function generate() {
  if (!props.productId) {
    toast("请先选择商品", "error");
    return;
  }
  // 生成中禁止重复发起（按钮已禁用，此处再兜底一次）
  if (generating.value || getGeneration("liveScript", props.productId)?.pending) return;
  generating.value = true;
  generateError.value = false;
  statusText.value = "生成中...";
  startGeneration("liveScript", props.productId);
  try {
    const data = await apiPost(`/products/${props.productId}/live-scripts`);
    statusText.value = data.status === "fallback" ? "已返回本地兜底" : "生成完成";
    script.value = data;
    // 完成状态写入模块级任务（由任务 watcher 统一刷新历史）
    finishGeneration("liveScript", props.productId, { result: data });
  } catch (e) {
    generateError.value = true;
    script.value = null;
    statusText.value = "生成失败";
    finishGeneration("liveScript", props.productId, { error: true });
  } finally {
    generating.value = false;
  }
}

async function loadHistory() {
  if (!props.productId) return;
  historyLoading.value = true;
  historyError.value = false;
  try {
    history.value = await apiGet(`/products/${props.productId}/live-scripts`);
  } catch (e) {
    historyError.value = true;
    history.value = [];
  } finally {
    historyLoading.value = false;
  }
}

async function viewHistory(id) {
  try {
    const data = await apiGet(`/live-scripts/${id}`);
    statusText.value = "已加载历史话术";
    script.value = data;
  } catch (e) {
    // 忽略，保持原展示
  }
}

// 切换商品时重置话术状态（与旧页面一致）
watch(
  () => props.productId,
  (id) => {
    generating.value = false;
    statusText.value = "";
    script.value = null;
    generateError.value = false;
    history.value = [];
    if (id) loadHistory();
  },
  { immediate: true }
);

// 生成任务状态同步（跨 tab 切换保持，按 productId 隔离）：
// 挂载时恢复「生成中」或已完成结果；后台请求完成后同步 UI 并刷新历史。
watch(
  () => getGeneration("liveScript", props.productId),
  (task) => {
    if (!task) return;
    if (task.pending) {
      if (!generating.value) {
        generating.value = true;
        statusText.value = "生成仍在进行，请稍候。";
      }
      return;
    }
    generating.value = false;
    if (task.error) {
      generateError.value = true;
      script.value = null;
      statusText.value = "生成失败";
    } else if (task.result) {
      generateError.value = false;
      script.value = task.result;
      statusText.value = task.result.status === "fallback" ? "已返回本地兜底" : "生成完成";
      loadHistory();
    }
  },
  { immediate: true }
);
</script>

<style scoped>
.gen-gate {
  margin-bottom: 10px;
}
.status-line {
  color: var(--gray-500);
  font-size: 13px;
  margin-bottom: 6px;
}
.script-card .empty {
  padding: 16px;
}
.script-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.script-meta b {
  font-size: 13px;
}
.fallback-warning {
  margin-bottom: 8px;
}
.history-head {
  font-weight: 700;
  font-size: 13px;
  margin: 12px 0 6px;
}
.history-info {
  min-width: 0;
}
.history-info b {
  font-size: 13px;
}
.history-info .tag {
  margin-left: 6px;
}
</style>
