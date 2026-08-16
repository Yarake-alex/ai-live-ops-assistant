<template>
  <div class="material-upload">
    <input
      ref="fileInput"
      type="file"
      accept=".pdf,.txt,.md,.csv"
      multiple
      style="display: none"
      @change="onFileSelected"
    />
    <button class="upload-btn" :disabled="uploading" @click="openPicker">
      {{ uploading ? "上传中…" : "上传素材" }}
    </button>
    <div class="upload-status">{{ statusText }}</div>

    <!-- 上传确认弹窗：与旧页面流程一致 -->
    <div v-if="confirmVisible" class="confirm-overlay" @click.self="cancel">
      <div class="confirm-box">
        <div class="confirm-head">
          <h3>确认上传直播素材</h3>
          <button class="close-btn" @click="cancel">✕</button>
        </div>
        <div class="confirm-body">
          <div class="count-line">本次选择 {{ pendingFiles.length }} 个文件</div>
          <div class="file-list">
            <div v-for="f in pendingFiles" :key="f.name" class="file-row">· {{ f.name }}</div>
          </div>
          <div v-if="dupNames.length" class="warn-red">
            本次选择中包含重复文件，请重新选择<br />{{ dupNames.join("、") }}
          </div>
          <div v-if="overlapNames.length" class="warn-amber">
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
import { ref } from "vue";
import { apiRequest, SessionExpiredError } from "../api/client";

const emit = defineEmits(["uploaded"]);

const fileInput = ref(null);
const uploading = ref(false);
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

async function onFileSelected(event) {
  const files = Array.from(event.target.files || []);
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
.material-upload {
  margin-top: 12px;
}
.upload-btn {
  padding: 6px 16px;
  font-size: 13px;
  border: none;
  border-radius: 6px;
  background: #16a34a;
  color: #fff;
  cursor: pointer;
}
.upload-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.upload-status {
  margin-top: 6px;
  font-size: 12px;
  color: #777;
}
.confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.confirm-box {
  width: min(520px, calc(100vw - 32px));
  max-height: 85vh;
  overflow-y: auto;
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
}
.confirm-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.confirm-head h3 {
  margin: 0;
  font-size: 15px;
}
.close-btn {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 14px;
  color: #777;
}
.count-line {
  font-size: 13px;
  margin-bottom: 6px;
}
.file-list {
  max-height: 180px;
  overflow-y: auto;
  font-size: 12px;
  color: #777;
  margin-bottom: 8px;
}
.file-row {
  word-break: break-all;
}
.warn-red {
  background: #fef2f2;
  color: #991b1b;
  padding: 8px;
  border-radius: 6px;
  font-size: 12px;
  margin-bottom: 8px;
}
.warn-amber {
  background: #fffbeb;
  color: #92400e;
  padding: 8px;
  border-radius: 6px;
  font-size: 12px;
  margin-bottom: 8px;
}
.confirm-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 12px;
}
.light-btn {
  padding: 6px 14px;
  font-size: 13px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
  color: #555;
  cursor: pointer;
}
.primary-btn {
  padding: 6px 14px;
  font-size: 13px;
  border: none;
  border-radius: 6px;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
}
.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
