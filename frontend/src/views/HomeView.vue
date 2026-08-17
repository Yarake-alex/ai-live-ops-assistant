<template>
  <section class="about-view container">
    <div class="card about-card">
      <div class="card-head">
        <h3>关于本系统</h3>
      </div>
      <p class="about-desc">
        AI 直播运营助手 MVP —— 面向直播电商运营场景的 AI 演示系统：商品资料维护、资料文档问答（语义检索 +
        基础检索降级）、开播话术、评论助手、直播复盘、资料完整度、问题洞察与运营建议，
        把「开播前 → 直播中 → 下播后」串成一条可演示的轻量工作流。
      </p>
      <dl class="about-meta">
        <div class="meta-row">
          <dt class="meta-label">当前版本</dt>
          <dd>直播运营 V4 · 前端 Vue3（V5 迁移完成）· V6 UI 统一优化</dd>
        </div>
        <div class="meta-row">
          <dt class="meta-label">技术栈</dt>
          <dd>FastAPI + SQLAlchemy · Vue3 + Vite（无 UI 框架、无状态库）</dd>
        </div>
        <div class="meta-row">
          <dt class="meta-label">旧版入口</dt>
          <dd>旧版单页前端保留为回退入口 <code>/legacy</code></dd>
        </div>
      </dl>
    </div>
  </section>
</template>

<script setup>
// V6 阶段 2：原「骨架页」占位改为「关于/版本信息」，移除未完成感文案。
// V6 阶段 6：窄内容阅读布局（约 760px），描述列表呈现版本/技术栈/旧版入口。
</script>

<style scoped>
/* 信息较少的页面：统一容器内居中窄阅读宽度，不横跨整屏 */
.about-card {
  max-width: 760px;
  margin: 0 auto;
}
.about-desc {
  margin: 0 0 16px;
  color: var(--gray-600);
  font-size: 14px;
  line-height: 1.9;
}
.about-meta {
  margin: 0;
  border-top: 1px solid var(--gray-100);
  padding-top: 14px;
}
.meta-row {
  display: flex;
  gap: 12px;
  margin: 0;
  padding: 6px 0;
  font-size: 13px;
  color: var(--gray-600);
}
.meta-label {
  flex-shrink: 0;
  width: 72px;
  color: var(--gray-400);
  font-size: 12px;
}
.meta-row dd {
  margin: 0;
  min-width: 0;
  word-break: break-all;
}
code {
  background: var(--gray-100);
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 12px;
  color: var(--gray-700);
}
</style>
