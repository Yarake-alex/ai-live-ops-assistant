<template>
  <div class="csv-tools">
    <input ref="fileInput" type="file" accept=".csv" style="display: none" @change="onFileSelected" />
    <div class="csv-buttons">
      <button class="light-btn" :disabled="importing || exporting" @click="openPicker">
        {{ importing ? "导入中..." : "📥 导入商品 CSV" }}
      </button>
      <button class="light-btn" :disabled="importing || exporting" @click="doExport">
        {{ exporting ? "导出中..." : "📤 导出商品 CSV" }}
      </button>
    </div>
    <div class="muted-tip">
      支持 CSV 批量导入导出，仅「商品名称」为必填。
      <details class="header-details">
        <summary>查看表头说明</summary>
        <div class="header-detail-text">
          表头支持英文（name, price, selling_points, target_audience, pain_points, promotion, stock, live_status, notes）或中文（商品名称、价格、核心卖点、适用人群、用户痛点、优惠信息、库存、直播状态、备注）。
        </div>
      </details>
    </div>
  </div>
</template>

<script setup>
// 阶段 5.3b：商品 CSV 导入导出（与旧页面一致）：
// 导入 POST /products/import（FormData，逐个汇总提示）；导出 GET /products/export（blob 下载）。
import { ref } from "vue";
import { apiRequest, ApiError, SessionExpiredError } from "../api/client";

const emit = defineEmits(["imported"]);

const fileInput = ref(null);
const importing = ref(false);
const exporting = ref(false);

function openPicker() {
  if (importing.value || exporting.value) return;
  fileInput.value?.click();
}

async function onFileSelected(event) {
  const file = event.target.files[0];
  if (!file) return;
  importing.value = true;
  const formData = new FormData();
  formData.append("file", file);
  try {
    const data = await apiRequest("/products/import", { method: "POST", body: formData });
    let msg = `导入完成！\n创建：${data.created} 条\n跳过（重复）：${data.skipped} 条`;
    if (data.errors && data.errors.length) {
      msg += `\n错误：${data.errors.length} 条`;
      const errDetails = data.errors
        .slice(0, 5)
        .map((e) => `  第${e.row}行：${e.reason}`)
        .join("\n");
      msg += `\n\n错误详情（最多显示5条）：\n${errDetails}`;
      if (data.errors.length > 5) {
        msg += `\n  ...还有 ${data.errors.length - 5} 条错误`;
      }
    }
    alert(msg);
    emit("imported");
  } catch (e) {
    if (e instanceof SessionExpiredError) {
      alert(e.message);
    } else if (e instanceof ApiError) {
      alert(e.detail || "导入失败");
    } else {
      alert("网络错误，导入失败");
    }
  } finally {
    importing.value = false;
    if (fileInput.value) fileInput.value.value = "";
  }
}

async function doExport() {
  if (importing.value || exporting.value) return;
  exporting.value = true;
  try {
    const res = await fetch("/products/export", { credentials: "include" });
    if (res.status === 401) {
      alert("登录已失效，请重新登录");
      return;
    }
    if (!res.ok) {
      let detail = "导出失败";
      try {
        const err = await res.json();
        if (err.detail) detail = err.detail;
      } catch {
        // 非 JSON 响应，保持默认文案
      }
      alert(detail);
      return;
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "products_export.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    alert("网络错误，导出失败");
  } finally {
    exporting.value = false;
  }
}
</script>

<style scoped>
.csv-tools {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.csv-buttons {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
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
.light-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.muted-tip {
  color: #777;
  font-size: 12px;
  min-width: 0;
}
.header-details {
  display: inline;
  margin-left: 6px;
}
.header-details summary {
  cursor: pointer;
  color: #2563eb;
  display: inline;
}
.header-detail-text {
  margin-top: 6px;
}
</style>
