<template>
  <section class="materials-view container">
    <div class="view-head">
      <div>
        <h2 class="view-title">直播素材库</h2>
        <p class="view-desc">上传直播资料用于资料问答，整理后可辅助话术与评论回复</p>
      </div>
    </div>

    <!-- 素材列表：单一业务面板，搜索与整理操作随列表归位 -->
    <div class="card">
      <div class="card-head materials-list-head">
        <div>
          <h3><Icon name="folder" size="15" class="head-icon" /> 素材列表</h3>
          <div class="materials-summary" aria-label="素材库摘要">
            <span class="summary-item"><b>{{ docs.length }}</b> 个文件</span>
            <span class="summary-item"><b>{{ totalChunks }}</b> 个片段</span>
            <span v-if="hasIndexStatus" class="summary-item">
              <b>{{ indexedChunks }}</b>/{{ indexableChunks }} 已整理
            </span>
          </div>
        </div>
        <div class="list-head-right">
          <SearchBox v-model="q" @search="loadDocs" />
        </div>
      </div>
      <MaterialList
        :docs="docs"
        :loading="loading"
        :error="error"
        :query="q"
        :busy="busy"
        @view-chunks="previewFilename = $event"
        @delete-doc="onDeleteDoc"
      />
      <MaterialChunksPreview :filename="previewFilename" @close="previewFilename = ''" />
      <div class="list-toolbar">
        <MaterialManage :doc-count="docs.length" @reorganized="loadDocs" @cleared="onCleared" />
      </div>
    </div>

    <!-- 上传与问答：按工作流并列的两个业务面板 -->
    <div class="materials-grid">
      <MaterialUpload @uploaded="loadDocs" />
      <MaterialQa :key="qaResetKey" />
    </div>
  </section>
</template>

<script setup>
// 阶段 3.1-3.4 + 5.1：迁移「直播素材库」列表、搜索、上传确认、片段预览、
// 删除/清空/重新整理与资料问答。
// 接口与旧页面完全一致：GET /rag/documents（可选 ?q= 参数）、POST /rag/upload、
// GET /rag/documents/{filename}/chunks、DELETE /rag/documents/{filename}、
// DELETE /rag/documents、POST /rag/reindex、POST /rag/ask，返回结构不变。
// 旧页面 static/index.html 继续可用。
// V6 阶段 5：列表面板（搜索/预览/整理归位）、上传区（拖拽/选择容器边界）+
// 资料问答并列，页面铺满内容区。上传入口仅保留上传面板一处（与旧页面一致）。
import { computed, ref, onMounted } from "vue";
import { apiGet, apiRequest } from "../api/client";
import { toast, confirmDialog } from "../state/feedback";
import Icon from "../components/Icon.vue";
import SearchBox from "../components/SearchBox.vue";
import MaterialList from "../components/MaterialList.vue";
import MaterialUpload from "../components/MaterialUpload.vue";
import MaterialChunksPreview from "../components/MaterialChunksPreview.vue";
import MaterialManage from "../components/MaterialManage.vue";
import MaterialQa from "../components/MaterialQa.vue";

const previewFilename = ref("");
const busy = ref(false);
// 清空素材库后重置资料问答组件状态（与旧页面清空问答结果区一致）
const qaResetKey = ref(0);

async function onDeleteDoc(filename) {
  if (busy.value) return;
  const ok = await confirmDialog(`确定要删除资料「${filename}」吗？删除后，该资料不会再参与资料检索。`, {
    danger: true,
  });
  if (!ok) return;
  busy.value = true;
  try {
    await apiRequest(`/rag/documents/${encodeURIComponent(filename)}`, { method: "DELETE" });
    // 删除正在预览的文件时清空预览（与旧页面一致）
    if (previewFilename.value === filename) previewFilename.value = "";
    toast("资料已删除", "success");
    await loadDocs();
  } catch (e) {
    toast("删除失败，请稍后重试。", "error");
  } finally {
    busy.value = false;
  }
}

function onCleared() {
  // 清空素材库后预览与问答结果一并清空（与旧页面一致）
  previewFilename.value = "";
  qaResetKey.value += 1;
  loadDocs();
}

const q = ref("");
const docs = ref([]);
const loading = ref(false);
const error = ref("");

const totalChunks = computed(() => docs.value.reduce((total, doc) => total + (Number(doc.chunks) || 0), 0));
const indexableDocs = computed(() => docs.value.filter((doc) => doc.vector_indexed != null));
const indexableChunks = computed(() => indexableDocs.value.reduce((total, doc) => total + (Number(doc.chunks) || 0), 0));
const indexedChunks = computed(() => indexableDocs.value.reduce((total, doc) => total + (Number(doc.vector_indexed) || 0), 0));
const hasIndexStatus = computed(() => indexableDocs.value.length > 0);

async function loadDocs() {
  loading.value = true;
  error.value = "";
  try {
    const trimmed = q.value.trim();
    const url = trimmed
      ? `/rag/documents?q=${encodeURIComponent(trimmed)}`
      : "/rag/documents";
    docs.value = await apiGet(url);
  } catch (e) {
    error.value = "素材列表加载失败，请稍后重试。";
    docs.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(loadDocs);
</script>

<style scoped>
.materials-list-head {
  align-items: flex-start;
}
.materials-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 0;
  margin-top: 6px;
  color: var(--gray-500);
  font-size: var(--text-xs);
}
.summary-item {
  display: inline-flex;
  gap: 4px;
  padding: 0 8px;
  white-space: nowrap;
}
.summary-item:first-child {
  padding-left: 0;
}
.summary-item + .summary-item {
  border-left: 1px solid var(--gray-200);
}
.summary-item b {
  color: var(--gray-700);
  font-weight: 600;
}
.list-head-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex: 1 1 360px;
  flex-wrap: wrap;
}
.list-toolbar {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--gray-100);
  display: flex;
  justify-content: flex-end;
}
.materials-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
  gap: 16px;
  margin-top: 16px;
  align-items: stretch;
}
@media (max-width: 900px) {
  .materials-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 768px) {
  .list-head-right {
    justify-content: flex-start;
  }
}
</style>
