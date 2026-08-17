<template>
  <div class="ai-result-content">
    <div class="ai-result-toolbar">
      <span class="ai-result-label">生成内容</span>
      <button class="light-btn copy-btn" type="button" @click="copyContent">
        <Icon :name="copied ? 'check' : 'copy'" size="13" />
        {{ copied ? "已复制" : "复制内容" }}
      </button>
    </div>
    <!-- html 仅由 renderSafeMarkdown() 生成：原始模型文本已被逐段 HTML 转义。 -->
    <div class="ai-markdown" v-html="html"></div>
  </div>
</template>

<script setup>
// 统一 AI 内容展示：受控 Markdown 子集 + 可读纯文本复制。
// 禁止将未经处理的模型内容直接 v-html。
import { computed, ref } from "vue";
import Icon from "./Icon.vue";
import { renderSafeMarkdown, markdownToPlainText } from "../utils/safeMarkdown";

const props = defineProps({
  content: { type: String, default: "" },
});

const html = computed(() => renderSafeMarkdown(props.content));
const copied = ref(false);
let copiedTimer = null;

async function copyContent() {
  const text = markdownToPlainText(props.content);
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {
    // Clipboard API 不可用时使用短生命周期 textarea 兼容旧浏览器；复制的仍是纯文本。
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }
  copied.value = true;
  clearTimeout(copiedTimer);
  copiedTimer = setTimeout(() => {
    copied.value = false;
  }, 1600);
}
</script>

<style scoped>
.ai-result-content {
  min-width: 0;
}
.ai-result-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.ai-result-label {
  color: var(--gray-500);
  font-size: 13px;
}
.copy-btn {
  flex-shrink: 0;
  min-height: 32px;
  padding: 5px 10px;
  font-size: 13px;
}
.ai-markdown {
  color: var(--gray-700);
  font-size: 14px;
  line-height: 1.8;
  overflow-wrap: anywhere;
  word-break: break-word;
}
.ai-markdown :deep(h1),
.ai-markdown :deep(h2) {
  margin: 18px 0 8px;
  color: var(--gray-900);
  line-height: 1.45;
}
.ai-markdown :deep(h1:first-child),
.ai-markdown :deep(h2:first-child) {
  margin-top: 0;
}
.ai-markdown :deep(h1) {
  font-size: 16px;
  font-weight: 700;
}
.ai-markdown :deep(h2) {
  padding-left: 9px;
  border-left: 2px solid var(--primary-border);
  font-size: 14px;
  font-weight: 700;
}
.ai-markdown :deep(p) {
  margin: 0 0 10px;
}
.ai-markdown :deep(ul),
.ai-markdown :deep(ol) {
  margin: 0 0 10px;
  padding-left: 22px;
}
.ai-markdown :deep(li + li) {
  margin-top: 3px;
}
.ai-markdown :deep(strong) {
  color: var(--gray-900);
  font-weight: 700;
}
.ai-markdown :deep(code) {
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--gray-100);
  color: var(--gray-700);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.92em;
}
.ai-markdown :deep(blockquote) {
  margin: 0 0 10px;
  padding: 7px 10px;
  border-left: 2px solid var(--primary-border);
  background: var(--primary-soft);
  color: var(--gray-600);
}
.ai-markdown :deep(hr) {
  height: 1px;
  margin: 16px 0;
  border: 0;
  background: var(--gray-200);
}
.ai-markdown :deep(.ai-table-wrap) {
  max-width: 100%;
  margin: 10px 0;
  overflow-x: auto;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-sm);
}
.ai-markdown :deep(table) {
  width: 100%;
  min-width: 420px;
  border-collapse: collapse;
  font-size: 13px;
}
.ai-markdown :deep(th),
.ai-markdown :deep(td) {
  padding: 8px 10px;
  border-bottom: 1px solid var(--gray-100);
  text-align: left;
  vertical-align: top;
}
.ai-markdown :deep(th) {
  background: var(--gray-50);
  color: var(--gray-700);
  font-weight: 600;
}
.ai-markdown :deep(tr:last-child td) {
  border-bottom: none;
}
@media (max-width: 390px) {
  .ai-result-toolbar {
    align-items: flex-start;
  }
  .ai-markdown :deep(h1) {
    font-size: 15px;
  }
}
</style>
