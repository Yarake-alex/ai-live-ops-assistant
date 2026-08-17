<template>
  <section class="about-view">
    <div class="card about-card">
      <div class="card-head">
        <h3>关于本系统</h3>
      </div>
      <p class="about-desc">
        AI 直播运营助手 MVP —— 面向直播电商运营场景的 AI 演示系统：商品资料维护、资料文档问答（语义检索 +
        基础检索降级）、开播话术、评论助手、直播复盘、资料完整度、问题洞察与运营建议，
        把「开播前 → 直播中 → 下播后」串成一条可演示的轻量工作流。
      </p>
      <div class="about-meta">
        <div class="meta-row"><span class="meta-label">当前版本</span>直播运营 V4 · 前端 Vue3（V5 迁移完成）· V6 UI 统一优化</div>
        <div class="meta-row"><span class="meta-label">技术栈</span>FastAPI + SQLAlchemy · Vue3 + Vite（无 UI 框架、无状态库）</div>
        <div class="meta-row"><span class="meta-label">旧版入口</span>旧版单页前端保留为回退入口 <code>/legacy</code></div>
      </div>
    </div>
  </section>
</template>

<script setup>
// V6 阶段 2：原「骨架页」占位改为「关于/版本信息」，移除未完成感文案。
</script>

<style scoped>
.about-view {
  max-width: var(--content-max);
  margin: 0 auto;
  padding: 24px 20px;
}
.about-desc {
  margin: 0 0 16px;
  color: var(--gray-600);
  font-size: 14px;
  line-height: 1.9;
}
.about-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-top: 1px solid var(--gray-100);
  padding-top: 14px;
}
.meta-row {
  font-size: 13px;
  color: var(--gray-600);
}
.meta-label {
  display: inline-block;
  min-width: 72px;
  color: var(--gray-400);
  font-size: 12px;
}
code {
  background: var(--gray-100);
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 12px;
  color: var(--gray-700);
}
</style>
