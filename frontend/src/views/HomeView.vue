<template>
  <section class="home-view">
    <h2>AI 直播运营助手 · Vue3 前端骨架</h2>
    <p>V5 阶段 2：基础层（API client / 会话状态 / 布局壳）已就绪，业务页面尚未迁移。</p>
    <p>当前演示仍使用原 static/index.html 单页版本。</p>
  </section>
</template>

<script setup>
// 占位页：无业务逻辑。
</script>

<style scoped>
.home-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 64px 24px;
  color: #333;
}
h2 {
  font-size: 20px;
  margin: 0;
}
p {
  margin: 0;
  color: #777;
  font-size: 14px;
}
</style>
