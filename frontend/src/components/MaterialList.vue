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
      <div v-for="d in docs" :key="d.filename" class="doc-entry">
        <div class="row-item">
          <div class="item-info">
            <b><Icon name="file" size="13" class="doc-file-icon" /> {{ d.filename }}</b>
            <div class="muted">片段：{{ d.chunks }} 个 · {{ vecInfo(d) }}{{ updatedInfo(d) }}</div>
            <div v-if="d.preview" class="muted item-preview">{{ d.preview }}…</div>
          </div>
          <div class="item-actions">
            <button class="light-btn" :disabled="busy" @click="togglePreview(d.filename)">
              {{ expandedFilename === d.filename ? "收起片段" : "查看片段" }}
            </button>
            <button class="danger-btn" :disabled="busy" @click="$emit('delete-doc', d.filename)">删除</button>
          </div>
        </div>

        <!-- 片段预览：在当前文件 item 下方内联展开（同列表只展开一个文件） -->
        <MaterialChunksPreview v-if="expandedFilename === d.filename" :filename="d.filename" />
      </div>
    </div>
  </div>
</template>

<script setup>
// 阶段 3.1 + 3.3 + 3.4：列表展示（文件名 / 片段数 / 整理进度 / 更新时间 / 内容预览）
// + 查看片段入口 + 删除入口（删除确认与调用由父组件处理）。
// V6：内容预览截断为最多 2 行；片段预览改为在当前文件 item 下方内联展开，
// 列表内只展开一个文件；搜索/刷新/删除/清空后自动清理失效的展开状态。
import { ref, watch } from "vue";
import Icon from "./Icon.vue";
import MaterialChunksPreview from "./MaterialChunksPreview.vue";

const props = defineProps({
  docs: { type: Array, default: () => [] },
  loading: Boolean,
  error: String,
  query: String,
  busy: Boolean,
});
defineEmits(["delete-doc"]);

const expandedFilename = ref("");

function togglePreview(filename) {
  expandedFilename.value = expandedFilename.value === filename ? "" : filename;
}

// 列表变化（搜索/刷新/删除/清空）后，展开的文件已不存在时自动收起
watch(
  () => props.docs,
  (list) => {
    if (expandedFilename.value && !list.some((d) => d.filename === expandedFilename.value)) {
      expandedFilename.value = "";
    }
  }
);

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
/* 文件条目之间用轻分隔线区分，行内不再使用 row-item 自带底边框 */
.doc-entry + .doc-entry {
  border-top: 1px solid #eef1f5;
}
.doc-entry .row-item {
  border-bottom: none;
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
/* 内容预览最多 2 行，超出省略，避免单个文件撑高列表 */
.item-preview {
  margin-top: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-all;
}
</style>
