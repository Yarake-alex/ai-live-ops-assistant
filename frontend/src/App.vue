<template>
  <main class="scaffold">
    <h1>AI 直播运营助手 · Vue3 前端骨架</h1>
    <p>V5 阶段 1：仅搭建组件化基础设施，业务页面尚未迁移。</p>
    <p>当前演示仍使用原 static/index.html 单页版本。</p>
  </main>
</template>

<script setup>
// 最小骨架：不包含任何业务逻辑与状态库。
</script>

<style scoped>
.scaffold {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-family: system-ui, -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  color: #333;
}
h1 {
  font-size: 22px;
  margin: 0;
}
p {
  margin: 0;
  color: #777;
  font-size: 14px;
}
</style>
