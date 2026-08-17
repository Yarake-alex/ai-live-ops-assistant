<template>
  <div class="card upload-card">
    <div class="card-head">
      <h3><Icon name="upload" size="15" class="head-icon" /> 上传素材</h3>
      <span class="muted">支持 PDF / TXT / MD / CSV，可一次多选</span>
    </div>
    <input
      ref="fileInput"
      type="file"
      accept=".pdf,.txt,.md,.csv"
      multiple
      style="display: none"
      @change="onFileSelected"
    />
    <div
      class="drop-zone"
      :class="{ dragging }"
      @click="openPicker"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <Icon name="upload" size="22" class="drop-icon" />
      <div class="drop-text">点击选择文件，或将文件拖拽到此处</div>
    </div>
    <div class="upload-status">{{ statusText }}</div>

    <!-- 上传确认弹窗：与旧页面流程一致 -->
    <div v-if="confirmVisible" class="modal-overlay" @click.self="cancel">
      <div class="modal-box confirm-box">
        <div class="modal-head">
          <h3>确认上传直播素材</h3>
          <button class="close-btn" @click="cancel"><Icon name="x" size="14" /></button>
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
          <button class="light-btn" :disabled="uploading" @click="cancel">取消</button>
          <button class="primary-btn" :disabled="dupNames.length > 0 || uploading" @click="confirmUpload">
            {{ uploading ? "上传中…" : "确认上传" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// 阶段 3.2：迁移直播素材上传确认（与旧页面流程一致）：
// 选文件 → 确认弹窗（同批重复拦截 / 同名覆盖提醒）→ 逐个 FormData 上传 POST /rag/upload。
// 单个文件失败不影响后续文件；上传成功后通知父组件刷新列表。
// V6：上传区面板化（拖拽/选择容器边界）；对外暴露 openPicker 供页面标题区「上传素材」调用。
import { ref } from "vue";
import { apiRequest, SessionExpiredError } from "../api/client";
import Icon from "./Icon.vue";

const emit = defineEmits(["uploaded"]);

const fileInput = ref(null);
const uploading = ref(false);
const dragging = ref(false);
const statusText = ref("尚未选择素材文件");

const confirmVisible = ref(false);
const pendingFiles = ref([]);
const dupNames = ref([]);
const overlapNames = ref([]);

function updateStatusText(files) {
  if (!files.length) {
    statusText.value = "尚未选择素材文件";
  } else if (files.length === 1) {
    statusText.value = `已选择 1 个文件：${files[0].name}`;
  } else {
    statusText.value = `已选择 ${files.length} 个文件`;
  }
}

function openPicker() {
  if (uploading.value) return;
  fileInput.value?.click();
}

defineExpose({ openPicker });

function onFileSelected(event) {
  handleFiles(Array.from(event.target.files || []));
}

function onDrop(event) {
  dragging.value = false;
  handleFiles(Array.from(event.dataTransfer.files || []));
}

async function handleFiles(files) {
  updateStatusText(files);
  if (!files.length) return;

  // 拉取已有文档名用于同名提醒；失败不阻塞上传确认
  let existingNames = [];
  try {
    const docs = await apiRequest("/rag/documents");
    existingNames = (docs || []).map((d) => d.filename);
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

function cancel() {
  if (uploading.value) return;
  confirmVisible.value = false;
  pendingFiles.value = [];
  dupNames.value = [];
  overlapNames.value = [];
  if (fileInput.value) fileInput.value.value = "";
  updateStatusText([]);
}

async function confirmUpload() {
  const files = pendingFiles.value;
  if (!files.length || dupNames.value.length || uploading.value) return;

  uploading.value = true;
  const failed = [];
  let successCount = 0;

  for (const file of files) {
    const formData = new FormData();
    formData.append("file", file);
    try {
      await apiRequest("/rag/upload", { method: "POST", body: formData });
      successCount += 1;
    } catch (e) {
      if (e instanceof SessionExpiredError) {
        statusText.value = e.message;
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

  if (successCount === files.length) {
    statusText.value = `上传完成：${successCount} 个文件已加入素材库`;
  } else if (successCount > 0) {
    statusText.value = `上传完成：${successCount} 个成功，${failed.length} 个失败。失败文件：${failed.join("、")}`;
  } else {
    statusText.value = `上传失败：${failed.length} 个文件未能上传。失败文件：${failed.join("、")}`;
  }

  emit("uploaded");
}
</script>

<style scoped>
.upload-card {
  display: flex;
  flex-direction: column;
}
.drop-zone {
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  padding: 32px 16px;
  text-align: center;
  cursor: pointer;
  background: var(--gray-50);
  transition: border-color 0.15s ease, background-color 0.15s ease;
}
.drop-zone:hover,
.drop-zone.dragging {
  border-color: var(--primary);
  background: var(--primary-soft);
}
.drop-icon {
  color: var(--gray-400);
}
.drop-text {
  font-size: 13px;
  color: var(--gray-500);
  margin-top: 6px;
}
.upload-status {
  margin-top: 8px;
  font-size: 12px;
  color: var(--gray-500);
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
