<template>
  <section class="materials-view">
    <div class="materials-header">
      <h2>📁 直播素材库</h2>
      <SearchBox v-model="q" @search="loadDocs" />
    </div>
    <MaterialList :docs="docs" :loading="loading" :error="error" :query="q" @view-chunks="previewFilename = $event" />
    <MaterialChunksPreview :filename="previewFilename" @close="previewFilename = ''" />
    <MaterialUpload @uploaded="loadDocs" />
  </section>
</template>

<script setup>
// 阶段 3.1 + 3.2 + 3.3：迁移「直播素材库」列表、搜索、上传确认与片段预览。
// 接口与旧页面完全一致：GET /rag/documents（可选 ?q= 参数）、POST /rag/upload、
// GET /rag/documents/{filename}/chunks，返回结构不变。
// 删除等能力留待后续阶段迁移，旧页面 static/index.html 继续可用。
import { ref, onMounted } from "vue";
import { apiGet } from "../api/client";
import SearchBox from "../components/SearchBox.vue";
import MaterialList from "../components/MaterialList.vue";
import MaterialUpload from "../components/MaterialUpload.vue";
import MaterialChunksPreview from "../components/MaterialChunksPreview.vue";

const previewFilename = ref("");

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
  max-width: 960px;
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
</style>
