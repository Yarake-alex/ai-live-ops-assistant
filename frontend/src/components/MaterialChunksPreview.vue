<template>
  <div v-if="filename" class="chunks-preview">
    <div class="preview-head">
      <b>当前文件：{{ filename }}</b>
      <button class="close-btn" @click="$emit('close')">收起片段</button>
    </div>
    <div class="preview-body">
      <div v-if="loading" class="hint">加载片段...</div>
      <div v-else-if="error" class="hint hint-error">加载片段失败。</div>
      <div v-else-if="!chunks.length" class="hint">该资料暂无可预览片段</div>
      <template v-else>
        <div v-for="c in chunks" :key="c.chunk_index" class="chunk">
          <div class="chunk-meta">片段 {{ c.chunk_index }}{{ timeInfo(c) }}</div>
          <div class="chunk-content">{{ c.content }}</div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
// 阶段 3.3：素材片段预览（与旧页面交互一致）：
// GET /rag/documents/{filename}/chunks → 按顺序展示片段，空片段过滤，
// 无有效片段显示「该资料暂无可预览片段」，内容区内部滚动，可收起。
import { ref, watch } from "vue";
import { apiGet } from "../api/client";

const props = defineProps({
  filename: { type: String, default: "" },
});
defineEmits(["close"]);

const loading = ref(false);
const error = ref(false);
const chunks = ref([]);

watch(
  () => props.filename,
  async (fn) => {
    if (!fn) {
      chunks.value = [];
      return;
    }
    loading.value = true;
    error.value = false;
    chunks.value = [];
    try {
      const data = await apiGet(`/rag/documents/${encodeURIComponent(fn)}/chunks`);
      chunks.value = (data.chunks || []).filter((c) => c.content && c.content.trim());
    } catch (e) {
      error.value = true;
    } finally {
      loading.value = false;
    }
  },
  { immediate: true }
);

function timeInfo(c) {
  return c.created_at ? ` · ${c.created_at.slice(0, 16).replace("T", " ")}` : "";
}
</script>

<style scoped>
.chunks-preview {
  margin-top: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 12px 16px;
}
.preview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.preview-head b {
  font-size: 13px;
}
.close-btn {
  font-size: 12px;
  padding: 4px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
  color: #555;
  cursor: pointer;
}
.preview-body {
  max-height: 320px;
  overflow-y: auto;
}
.hint {
  padding: 24px 12px;
  text-align: center;
  color: #999;
  font-size: 13px;
}
.hint-error {
  color: #b91c1c;
}
.chunk {
  background: #f8f9fa;
  padding: 8px;
  margin: 6px 0;
  border-radius: 4px;
  font-size: 0.9em;
}
.chunk-meta {
  color: #777;
  font-size: 0.8em;
  margin-bottom: 4px;
}
.chunk-content {
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
