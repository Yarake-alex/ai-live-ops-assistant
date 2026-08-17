<template>
  <section class="materials-view">
    <div class="materials-header">
      <h2>📁 直播素材库</h2>
      <SearchBox v-model="q" @search="loadDocs" />
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
    <div class="materials-bottom">
      <MaterialUpload @uploaded="loadDocs" />
      <MaterialManage :doc-count="docs.length" @reorganized="loadDocs" @cleared="onCleared" />
    </div>
    <MaterialQa />
  </section>
</template>

<script setup>
// 阶段 3.1-3.4 + 5.1：迁移「直播素材库」列表、搜索、上传确认、片段预览、
// 删除/清空/重新整理与资料问答。
// 接口与旧页面完全一致：GET /rag/documents（可选 ?q= 参数）、POST /rag/upload、
// GET /rag/documents/{filename}/chunks、DELETE /rag/documents/{filename}、
// DELETE /rag/documents、POST /rag/reindex、POST /rag/ask，返回结构不变。
// 旧页面 static/index.html 继续可用。
import { ref, onMounted } from "vue";
import { apiGet, apiRequest } from "../api/client";
import SearchBox from "../components/SearchBox.vue";
import MaterialList from "../components/MaterialList.vue";
import MaterialUpload from "../components/MaterialUpload.vue";
import MaterialChunksPreview from "../components/MaterialChunksPreview.vue";
import MaterialManage from "../components/MaterialManage.vue";
import MaterialQa from "../components/MaterialQa.vue";

const previewFilename = ref("");
const busy = ref(false);

async function onDeleteDoc(filename) {
  if (busy.value) return;
  const ok = confirm(`确定要删除资料「${filename}」吗？删除后，该资料不会再参与资料检索。`);
  if (!ok) return;
  busy.value = true;
  try {
    await apiRequest(`/rag/documents/${encodeURIComponent(filename)}`, { method: "DELETE" });
    // 删除正在预览的文件时清空预览（与旧页面一致）
    if (previewFilename.value === filename) previewFilename.value = "";
    alert("资料已删除");
    await loadDocs();
  } catch (e) {
    alert("删除失败，请稍后重试。");
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
.materials-view {
  max-width: var(--content-max);
  margin: 0 auto;
  padding: 24px 20px;
}
.materials-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.materials-header h2 {
  margin: 0;
  font-size: 17px;
  color: #333;
}
.materials-bottom {
  display: flex;
  gap: 24px;
  align-items: flex-start;
  flex-wrap: wrap;
}
</style>
