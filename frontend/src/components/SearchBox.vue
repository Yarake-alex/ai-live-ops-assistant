<template>
  <div class="search-box">
    <span class="search-box-icon"><Icon name="search" size="14" /></span>
    <input
      v-model="model"
      type="text"
      placeholder="按文件名搜索..."
      @input="onInput"
      @keydown.enter="searchNow"
    />
    <button v-if="model" class="search-box-clear" title="清空搜索" @click="clear">×</button>
  </div>
</template>

<script setup>
// 与旧页面交互一致：输入 400ms 防抖搜索、Enter 立即搜索、× 清空并立即显示全部。
import { computed } from "vue";
import Icon from "./Icon.vue";

const props = defineProps({ modelValue: String });
const emit = defineEmits(["update:modelValue", "search"]);

const model = computed({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v),
});

let timer = null;

function onInput() {
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => emit("search"), 400);
}

function searchNow() {
  if (timer) clearTimeout(timer);
  emit("search");
}

function clear() {
  model.value = "";
  searchNow();
}
</script>

<style scoped>
.search-box {
  position: relative;
  flex: 1;
  min-width: 200px;
  max-width: 420px;
}
.search-box-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  display: inline-flex;
  color: var(--gray-400);
  pointer-events: none;
}
.search-box input {
  width: 100%;
  padding-left: 32px;
  padding-right: 28px;
}
.search-box-clear {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  border: none;
  background: none;
  cursor: pointer;
  font-size: 15px;
  color: #777;
}
</style>
