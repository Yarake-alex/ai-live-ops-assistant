<template>
  <div class="module-section">
    <div class="documents-head">
      <h4 class="embedded-title"><Icon name="book" size="14" class="head-icon" /> 商品资料文档</h4>
      <div class="head-actions">
        <button class="light-btn" :disabled="busy" @click="reorganize">
          {{ busy === "reorganize" ? "整理中…" : "重新整理资料" }}
        </button>
      </div>
    </div>

    <div class="muted-tip">支持一次选择多个 PDF / TXT / MD / CSV 文件；上传后可用于商品资料问答。</div>

    <div v-if="!productId" class="hint">选择商品后展示该商品的资料文档。</div>
    <div v-else-if="loading" class="hint">加载中…</div>
    <div v-else-if="error" class="hint hint-error">资料列表加载失败。</div>
    <div v-else-if="!docs.length" class="empty">
      <span class="empty-icon"><Icon name="file" size="28" /></span>
      <span>暂无资料，可上传 PDF / TXT / MD / CSV。</span>
    </div>
    <div v-else class="doc-list">
      <div v-for="d in docs" :key="d.filename" class="row-item">
        <div class="doc-info">
          <b><Icon name="file" size="13" class="doc-file-icon" /> {{ d.filename }}</b>
          <div class="muted">{{ d.chunks }} 个片段<span v-if="d.preview"> · {{ d.preview.slice(0, 40) }}…</span></div>
        </div>
        <div class="doc-actions">
          <button class="light-btn" :disabled="busy" @click="previewFilename = d.filename">查看片段</button>
          <button class="danger-btn" :disabled="busy" @click="onDeleteDoc(d.filename)">删除</button>
        </div>
      </div>
    </div>

    <!-- 片段预览（与旧页面一致：原地展示、可收起） -->
    <div v-if="previewFilename" class="chunks-preview">
      <div class="preview-head">
        <b>当前文件：{{ previewFilename }}</b>
        <button class="light-btn" @click="previewFilename = ''">收起片段</button>
      </div>
      <div class="preview-body">
        <div v-if="previewLoading" class="hint">加载片段...</div>
        <div v-else-if="previewError" class="hint hint-error">加载片段失败。</div>
        <div v-else-if="!chunks.length" class="hint">该资料暂无可预览片段</div>
        <template v-else>
          <div v-for="c in chunks" :key="c.chunk_index" class="chunk">
            <div class="chunk-meta">片段 {{ c.chunk_index }}{{ timeInfo(c) }}</div>
            <div class="chunk-content">{{ c.content }}</div>
          </div>
        </template>
      </div>
    </div>

    <!-- 上传操作区（列表底部，与素材库交互模式一致） -->
    <input
      ref="fileInput"
      type="file"
      accept=".pdf,.txt,.md,.csv"
      multiple
      style="display: none"
      @change="onFileSelected"
    />
    <div class="upload-area">
      <button class="primary-btn" :disabled="busy" @click="openPicker">
        <Icon name="upload" size="13" /> {{ uploading ? "上传中…" : "上传资料" }}
      </button>
      <span class="muted upload-status">{{ uploadStatusText }}</span>
    </div>

    <!-- 上传确认弹窗（与素材库一致：同批重复拦截 / 同名覆盖提醒） -->
    <div v-if="confirmVisible" class="modal-overlay" @click.self="cancelUpload">
      <div class="modal-box confirm-box">
        <div class="modal-head">
          <h3>确认上传商品资料</h3>
          <button class="close-btn" @click="cancelUpload"><Icon name="x" size="14" /></button>
        </div>
        <div class="confirm-body">
          <div class="count-line">本次选择 {{ pendingFiles.length }} 个文件</div>
          <div class="file-list">
            <div v-for="f in pendingFiles" :key="f.name" class="file-row">· {{ f.name }}</div>
          </div>
          <div v-if="dupNames.length" class="alert alert-danger">
            本次选择中包含重复文件，请重新选择<br />{{ dupNames.join("、") }}
          </div>
          <div v-if="overlapNames.length" class="alert alert-warning">
            以下文件已存在，继续上传将覆盖旧资料<br />{{ overlapNames.join("、") }}
          </div>
        </div>
        <div class="confirm-actions">
          <button class="light-btn" :disabled="uploading" @click="cancelUpload">取消</button>
          <button class="primary-btn" :disabled="dupNames.length > 0 || uploading" @click="confirmUpload">
            {{ uploading ? "上传中…" : "确认上传" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 阶段 5.7：商品资料文档完整能力（复刻旧页面，交互模式与素材库一致）：
// GET /products/{id}/knowledge/documents 列表；
// POST /products/{id}/knowledge/upload 逐个上传（确认弹窗）；
// GET /products/{id}/knowledge/documents/{filename}/chunks 片段预览；
// DELETE /products/{id}/knowledge/documents/{filename} 删除；
// POST /products/{id}/knowledge/documents/{filename}/reindex 逐个重新整理。
import { ref, watch } from "vue";
import { apiGet, apiRequest, SessionExpiredError } from "../api/client";
import { toast, confirmDialog } from "../state/feedback";
import Icon from "./Icon.vue";

const props = defineProps({
  productId: { type: Number, default: null },
});
const emit = defineEmits(["changed", "docs"]);

const docs = ref([]);
const loading = ref(false);
const error = ref(false);
const busy = ref(false);

// 片段预览
const previewFilename = ref("");
const previewLoading = ref(false);
const previewError = ref(false);
const chunks = ref([]);

// 上传
const fileInput = ref(null);
const uploading = ref(false);
const uploadStatusText = ref("尚未选择资料文件");
const confirmVisible = ref(false);
const pendingFiles = ref([]);
const dupNames = ref([]);
const overlapNames = ref([]);

function timeInfo(c) {
  return c.created_at ? ` · ${c.created_at.slice(0, 16).replace("T", " ")}` : "";
}

async function load() {
  if (!props.productId) return;
  loading.value = true;
  error.value = false;
  try {
    docs.value = await apiGet(`/products/${props.productId}/knowledge/documents`);
    emit("docs", docs.value.length);
  } catch (e) {
    error.value = true;
    docs.value = [];
  } finally {
    loading.value = false;
  }
}

// ─── 片段预览 ───
watch(previewFilename, async (fn) => {
  if (!fn) {
    chunks.value = [];
    return;
  }
  previewLoading.value = true;
  previewError.value = false;
  chunks.value = [];
  try {
    const data = await apiGet(
      `/products/${props.productId}/knowledge/documents/${encodeURIComponent(fn)}/chunks`
    );
    chunks.value = (data.chunks || []).filter((c) => c.content && c.content.trim());
  } catch (e) {
    previewError.value = true;
  } finally {
    previewLoading.value = false;
  }
});

// ─── 上传 ───
function openPicker() {
  if (busy.value || uploading.value) return;
  fileInput.value?.click();
}

function updateUploadStatusText(files) {
  if (!files.length) {
    uploadStatusText.value = "尚未选择资料文件";
  } else if (files.length === 1) {
    uploadStatusText.value = `已选择 1 个文件：${files[0].name}`;
  } else {
    uploadStatusText.value = `已选择 ${files.length} 个文件`;
  }
}

async function onFileSelected(event) {
  const files = Array.from(event.target.files || []);
  updateUploadStatusText(files);
  if (!files.length) return;

  let existingNames = [];
  try {
    const list = await apiGet(`/products/${props.productId}/knowledge/documents`);
    existingNames = (list || []).map((d) => d.filename);
  } catch (e) {
    console.warn("获取已有文档列表失败，跳过同名提醒:", e);
  }

  const counts = {};
  files.forEach((f) => {
    counts[f.name] = (counts[f.name] || 0) + 1;
  });
  dupNames.value = Object.keys(counts).filter((n) => counts[n] > 1);
  overlapNames.value = files.map((f) => f.name).filter((n) => existingNames.includes(n));

  pendingFiles.value = files;
  confirmVisible.value = true;
}

function cancelUpload() {
  if (uploading.value) return;
  confirmVisible.value = false;
  pendingFiles.value = [];
  dupNames.value = [];
  overlapNames.value = [];
  if (fileInput.value) fileInput.value.value = "";
  updateUploadStatusText([]);
}

async function confirmUpload() {
  const files = pendingFiles.value;
  if (!files.length || dupNames.value.length || uploading.value) return;

  uploading.value = true;
  busy.value = true;
  const failed = [];
  let successCount = 0;

  for (const file of files) {
    const formData = new FormData();
    formData.append("file", file);
    try {
      await apiRequest(`/products/${props.productId}/knowledge/upload`, {
        method: "POST",
        body: formData,
      });
      successCount += 1;
    } catch (e) {
      if (e instanceof SessionExpiredError) {
        uploadStatusText.value = e.message;
        break;
      }
      failed.push(file.name);
      console.warn("上传失败:", file.name, e);
    }
  }

  confirmVisible.value = false;
  pendingFiles.value = [];
  dupNames.value = [];
  overlapNames.value = [];
  if (fileInput.value) fileInput.value.value = "";
  uploading.value = false;
  busy.value = false;

  if (successCount === files.length) {
    uploadStatusText.value = `上传完成：${successCount} 个文件已加入资料`;
  } else if (successCount > 0) {
    uploadStatusText.value = `上传完成：${successCount} 个成功，${failed.length} 个失败。失败文件：${failed.join("、")}`;
  } else {
    uploadStatusText.value = `上传失败：${failed.length} 个文件未能上传。失败文件：${failed.join("、")}`;
  }

  // 覆盖了正在预览的文件时清空预览（与旧页面一致）
  if (files.some((f) => f.name === previewFilename.value)) {
    previewFilename.value = "";
  }
  await load();
  emit("changed");
}

// ─── 删除 ───
async function onDeleteDoc(filename) {
  if (busy.value) return;
  if (!(await confirmDialog(`确定删除资料「${filename}」吗？`, { danger: true }))) return;
  busy.value = true;
  try {
    await apiRequest(`/products/${props.productId}/knowledge/documents/${encodeURIComponent(filename)}`, {
      method: "DELETE",
    });
    if (previewFilename.value === filename) previewFilename.value = "";
    await load();
    emit("changed");
  } catch (e) {
    toast(e.message || "删除失败，请稍后重试。", "error");
  } finally {
    busy.value = false;
  }
}

// ─── 重新整理资料 ───
async function reorganize() {
  if (busy.value) return;
  if (!props.productId) return;
  if (!docs.value.length) {
    toast("当前商品暂无资料文档", "error");
    return;
  }

  busy.value = true;
  let okCount = 0;
  const failed = [];
  for (const d of docs.value) {
    try {
      const data = await apiRequest(
        `/products/${props.productId}/knowledge/documents/${encodeURIComponent(d.filename)}/reindex`,
        { method: "POST" }
      );
      if (data && data.reindexed) {
        okCount += 1;
      } else {
        failed.push(d.filename);
      }
    } catch (e) {
      failed.push(d.filename);
    }
  }

  let message;
  if (!failed.length) {
    message = `资料整理完成：${okCount} 个文件已更新`;
  } else if (okCount === 0) {
    message = `资料整理失败：${failed.length} 个文件未能整理。失败文件：${failed.join("、")}`;
  } else {
    message = `资料整理完成：${okCount} 个成功，${failed.length} 个失败。失败文件：${failed.join("、")}`;
  }
  busy.value = false;
  await load();
  emit("changed");
  toast(message, failed.length ? "error" : "success", 5000);
}

watch(() => props.productId, load, { immediate: true });
</script>

<style scoped>
.documents-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.head-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.muted-tip {
  color: var(--gray-500);
  font-size: 13px;
  margin-bottom: 6px;
}
.module-section .muted {
  font-size: 13px;
}
.doc-list {
  max-height: 360px;
  overflow-y: auto;
}
.doc-info {
  min-width: 0;
  flex: 1;
}
.doc-file-icon {
  color: var(--gray-400);
  vertical-align: -2px;
}
.doc-actions {
  flex-shrink: 0;
  display: flex;
  gap: 6px;
}
.chunks-preview {
  margin-top: 12px;
  border: 1px solid var(--gray-100);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  background: #fbfcfd;
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
.preview-body {
  max-height: 320px;
  overflow-y: auto;
}
.chunk {
  background: var(--gray-50);
  padding: 8px;
  margin: 6px 0;
  border-radius: var(--radius-sm);
  font-size: 0.9em;
}
.chunk-meta {
  color: var(--gray-500);
  font-size: 0.8em;
  margin-bottom: 4px;
}
.chunk-content {
  white-space: pre-wrap;
  word-break: break-all;
}
.upload-area {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--gray-100);
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.upload-status {
  margin-top: 0;
}
.confirm-box {
  width: min(520px, calc(100vw - 32px));
}
.count-line {
  font-size: 13px;
  margin-bottom: 6px;
}
.file-list {
  max-height: 180px;
  overflow-y: auto;
  font-size: 12px;
  color: var(--gray-500);
  margin-bottom: 8px;
}
.file-row {
  word-break: break-all;
}
.confirm-body .alert {
  margin-bottom: 8px;
}
.confirm-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
