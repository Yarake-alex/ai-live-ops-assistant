<template>
  <div v-if="filename" class="chunks-preview">
    <div class="preview-head">
      <b>当前文件：{{ filename }}</b>
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
// 无有效片段显示「该资料暂无可预览片段」，内容区内部滚动。
// V6：改为在文件 item 下方内联展开（浅主色背景 + 左侧主色竖线），
// 收起由列表行的「查看片段/收起片段」按钮控制，本组件不再自带收起按钮。
import { ref, watch } from "vue";
import { apiGet } from "../api/client";

const props = defineProps({
  filename: { type: String, default: "" },
});

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
/* 内联展开区：与普通文件 item 明显区分（浅主色背景 + 左侧 3px 主色竖线），
   总高度控制在 260-320px 内，片段区内部滚动。 */
.chunks-preview {
  margin: 4px 0 10px;
  border: 1px solid var(--primary-border);
  border-left: 3px solid var(--primary);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  background: var(--primary-soft);
}
.preview-head {
  margin-bottom: 8px;
}
.preview-head b {
  font-size: 13px;
  color: var(--gray-700);
}
.preview-body {
  max-height: 230px;
  overflow-y: auto;
}
.chunk {
  background: #fff;
  border: 1px solid var(--gray-100);
  padding: 8px;
  margin: 6px 0;
  border-radius: var(--radius-sm);
  font-size: 13px;
}
.chunk-meta {
  color: var(--gray-500);
  font-size: 13px;
  margin-bottom: 4px;
}
.chunk-content {
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
