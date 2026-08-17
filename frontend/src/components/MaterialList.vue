<template>
  <div class="material-list">
    <div v-if="loading" class="hint">加载中…</div>
    <div v-else-if="error" class="hint hint-error">{{ error }}</div>
    <div v-else-if="!docs.length" class="empty material-empty">
      <span class="empty-icon"><Icon :name="query.trim() ? 'search' : 'folder'" size="28" /></span>
      <span>{{ query.trim() ? `未找到匹配「${query.trim()}」的资料。` : "素材库暂未添加资料。" }}</span>
      <span class="empty-next">{{ query.trim() ? "尝试调整搜索关键词，或清空搜索后查看全部素材。" : "下一步：上传素材后即可进行资料问答。" }}</span>
    </div>
    <div v-else class="list-items">
      <div v-for="d in docs" :key="d.filename" class="row-item">
        <div class="item-info">
          <b><Icon name="file" size="13" class="doc-file-icon" /> {{ d.filename }}</b>
          <div class="muted">片段：{{ d.chunks }} 个 · {{ vecInfo(d) }}{{ updatedInfo(d) }}</div>
          <div v-if="d.preview" class="muted item-preview">{{ d.preview }}…</div>
        </div>
        <div class="item-actions">
          <button class="light-btn" :disabled="busy" @click="$emit('view-chunks', d.filename)">查看片段</button>
          <button class="danger-btn" :disabled="busy" @click="$emit('delete-doc', d.filename)">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 阶段 3.1 + 3.3 + 3.4：列表展示（文件名 / 片段数 / 整理进度 / 更新时间 / 内容预览）
// + 查看片段入口 + 删除入口（删除确认与调用由父组件处理）。
// V6：作为「素材列表」业务面板的内容体（面板外壳由父组件提供），空态统一。
import Icon from "./Icon.vue";

defineProps({
  docs: { type: Array, default: () => [] },
  loading: Boolean,
  error: String,
  query: String,
  busy: Boolean,
});
defineEmits(["view-chunks", "delete-doc"]);

function vecInfo(d) {
  return d.vector_indexed != null
    ? `资料整理进度：${d.vector_indexed}/${d.chunks}`
    : "资料整理功能未启用";
}

function updatedInfo(d) {
  return d.updated_at ? ` · 更新于 ${d.updated_at.slice(0, 16).replace("T", " ")}` : "";
}
</script>

<style scoped>
.material-list {
  min-height: 112px;
}
.material-empty {
  min-height: 112px;
  padding: 18px 16px;
  gap: 5px;
}
.empty-next {
  color: var(--gray-400);
  font-size: var(--text-xs);
}
.list-items {
  max-height: 420px;
  overflow-y: auto;
  padding-right: 4px;
}
.item-info {
  min-width: 0;
  flex: 1;
}
.doc-file-icon {
  color: var(--gray-400);
  vertical-align: -2px;
}
.item-actions {
  flex-shrink: 0;
  display: flex;
  gap: 6px;
}
.item-preview {
  margin-top: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
