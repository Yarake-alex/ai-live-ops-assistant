<template>
  <div class="documents-card">
    <div class="card-head">
      <h3>📚 商品资料文档</h3>
      <button class="light-btn" :disabled="loading" @click="load">刷新</button>
    </div>
    <div class="muted-tip">支持一次选择多个 PDF / TXT / MD / CSV 文件；上传后可用于商品资料问答。</div>
    <div v-if="!productId" class="hint">选择商品后展示该商品的资料文档。</div>
    <div v-else-if="loading" class="hint">加载中…</div>
    <div v-else-if="error" class="hint hint-error">资料列表加载失败。</div>
    <div v-else-if="!docs.length" class="hint">暂无资料，可上传 PDF / TXT / MD / CSV。</div>
    <div v-else class="doc-list">
      <div v-for="d in docs" :key="d.filename" class="doc-item">
        <div class="doc-info">
          <b>📄 {{ d.filename }}</b>
          <div class="muted">{{ d.chunks }} 个片段<span v-if="d.preview"> · {{ d.preview.slice(0, 40) }}…</span></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 阶段 4.2：商品资料文档列表（仅展示，与旧页面文案一致）：
// GET /products/{id}/knowledge/documents → [{filename, chunks, preview}]。
// 查看片段、删除、上传等操作留待后续阶段迁移。
import { ref, watch } from "vue";
import { apiGet } from "../api/client";

const props = defineProps({
  productId: { type: Number, default: null },
});

const loading = ref(false);
const error = ref(false);
const docs = ref([]);

async function load() {
  if (!props.productId) return;
  loading.value = true;
  error.value = false;
  try {
    docs.value = await apiGet(`/products/${props.productId}/knowledge/documents`);
  } catch (e) {
    error.value = true;
    docs.value = [];
  } finally {
    loading.value = false;
  }
}

watch(() => props.productId, load, { immediate: true });
</script>

<style scoped>
.documents-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
  margin-top: 12px;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.card-head h3 {
  margin: 0;
  font-size: 15px;
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
.light-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.muted-tip {
  color: #777;
  font-size: 12px;
  margin-bottom: 6px;
}
.hint {
  padding: 20px 4px;
  color: #999;
  font-size: 13px;
  text-align: center;
}
.hint-error {
  color: #b91c1c;
}
.doc-list {
  max-height: 360px;
  overflow-y: auto;
}
.doc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 4px;
  border-bottom: 1px solid #f3f4f6;
}
.doc-item:last-child {
  border-bottom: none;
}
.doc-info {
  min-width: 0;
  flex: 1;
}
.muted {
  color: #777;
  font-size: 11px;
}
</style>
