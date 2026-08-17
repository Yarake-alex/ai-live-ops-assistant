<template>
  <section class="materials-view container">
    <div class="view-head">
      <div>
        <h2 class="view-title">直播素材库</h2>
        <p class="view-desc">上传直播资料用于资料问答，整理后可辅助话术与评论回复</p>
      </div>
      <div class="view-actions">
        <button class="primary-btn" @click="uploadRef?.openPicker()">
          <Icon name="upload" size="14" /> 上传素材
        </button>
      </div>
    </div>

    <!-- 素材列表：单一业务面板，搜索与整理操作随列表归位 -->
    <div class="card">
      <div class="card-head">
        <h3><Icon name="folder" size="15" class="head-icon" /> 素材列表</h3>
        <div class="list-head-right">
          <span class="count-badge">{{ docs.length }} 个文件</span>
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
      <MaterialUpload ref="uploadRef" @uploaded="loadDocs" />
      <MaterialQa />
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
// V6 阶段 5：标题区（上传素材归位右上）、列表面板（搜索/预览/整理归位）、
// 上传区（拖拽/选择容器边界）+ 资料问答并列，页面铺满内容区。
import { ref, onMounted } from "vue";
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
const uploadRef = ref(null);

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
  // 清空素材库后预览一并清空（与旧页面一致）
  previewFilename.value = "";
  loadDocs();
}

const q = ref("");
const docs = ref([]);
const loading = ref(false);
const error = ref("");

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
.list-head-right {
  display: flex;
  align-items: center;
  gap: 10px;
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
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 16px;
  align-items: stretch;
}
@media (max-width: 900px) {
  .materials-grid {
    grid-template-columns: 1fr;
  }
}
</style>
