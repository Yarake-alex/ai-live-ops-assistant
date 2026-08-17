<template>
  <div class="material-manage">
    <button class="outline-btn" :disabled="busy" @click="reorganize">
      <Icon name="refresh" size="13" /> {{ busy === "reindex" ? "整理中…" : "重新整理素材" }}
    </button>
    <button class="danger-btn" :disabled="busy" @click="clearAll">清空全部</button>
  </div>
</template>

<script setup>
// 阶段 3.4：重新整理素材（POST /rag/reindex）与清空素材库（DELETE /rag/documents）。
// 文案与旧页面一致：确认提示、整理中禁用、成功/暂不可用提示；操作后通知父组件刷新。
// V6：无素材时两个按钮均给出明确提示（重新整理：当前暂无直播素材；
// 清空：当前暂无可清空素材），不表现为按钮失效。
import { ref } from "vue";
import { apiRequest } from "../api/client";
import { toast, confirmDialog } from "../state/feedback";
import Icon from "./Icon.vue";

const props = defineProps({
  docCount: { type: Number, default: 0 },
});
const emit = defineEmits(["reorganized", "cleared"]);

const busy = ref(""); // "" | "reindex" | "clear"

async function reorganize() {
  if (busy.value) return;
  if (!props.docCount) {
    toast("当前暂无直播素材", "error");
    return;
  }
  const ok = await confirmDialog(
    "将重新整理全部直播素材。\n\n此操作可能需要一些时间，期间素材问答仍可使用。\n\n确定要重新整理吗？"
  );
  if (!ok) return;

  busy.value = "reindex";
  try {
    const data = await apiRequest("/rag/reindex", { method: "POST" });
    if (data && data.reindexed) {
      toast("素材整理完成", "success");
    } else {
      toast("素材整理暂不可用，可继续使用基础资料检索", "error");
    }
    emit("reorganized");
  } catch (e) {
    toast("素材整理暂不可用，可继续使用基础资料检索", "error");
  } finally {
    busy.value = "";
  }
}

async function clearAll() {
  if (busy.value) return;
  if (!props.docCount) {
    toast("当前暂无可清空素材", "error");
    return;
  }
  const ok = await confirmDialog(
    "确定要清空全部素材库资料吗？清空后，所有已上传资料都不会再参与资料检索。",
    { danger: true }
  );
  if (!ok) return;

  busy.value = "clear";
  try {
    await apiRequest("/rag/documents", { method: "DELETE" });
    toast("素材库已清空", "success");
    emit("cleared");
  } catch (e) {
    toast("清空素材库失败，请稍后重试。", "error");
  } finally {
    busy.value = "";
  }
}
</script>

<style scoped>
.material-manage {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
