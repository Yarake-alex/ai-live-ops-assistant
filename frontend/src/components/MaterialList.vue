<template>
  <div class="material-list">
    <div v-if="loading" class="list-hint">加载中…</div>
    <div v-else-if="error" class="list-hint list-error">{{ error }}</div>
    <div v-else-if="!docs.length" class="list-hint">
      {{ query.trim() ? `未找到匹配「${query.trim()}」的资料。` : "暂无资料，请先上传。" }}
    </div>
    <div v-else class="list-items">
      <div v-for="d in docs" :key="d.filename" class="list-item">
        <div class="item-info">
          <b>📄 {{ d.filename }}</b>
          <div class="muted">片段：{{ d.chunks }} 个 · {{ vecInfo(d) }}{{ updatedInfo(d) }}</div>
          <div v-if="d.preview" class="muted item-preview">{{ d.preview }}…</div>
        </div>
        <div class="item-actions">
          <button class="light-btn" @click="$emit('view-chunks', d.filename)">查看片段</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 阶段 3.1 + 3.3：列表展示（文件名 / 片段数 / 整理进度 / 更新时间 / 内容预览）+ 查看片段入口。
// 删除等操作按钮留待后续阶段迁移，不在此实现。
defineProps({
  docs: { type: Array, default: () => [] },
  loading: Boolean,
  error: String,
  query: String,
});
defineEmits(["view-chunks"]);

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
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  min-height: 200px;
}
.list-hint {
  padding: 40px 16px;
  text-align: center;
  color: #999;
  font-size: 13px;
}
.list-error {
  color: #b91c1c;
}
.list-items {
  max-height: 420px;
  overflow-y: auto;
  padding: 8px 0;
}
.list-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid #f3f4f6;
}
.list-item:last-child {
  border-bottom: none;
}
.item-info {
  min-width: 0;
  flex: 1;
}
.item-actions {
  flex-shrink: 0;
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
.light-btn:hover {
  background: #f9fafb;
}
.muted {
  color: #777;
  font-size: 12px;
}
.item-preview {
  margin-top: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
