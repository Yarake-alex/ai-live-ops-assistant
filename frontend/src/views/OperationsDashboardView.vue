<template>
  <section class="dashboard-view">
    <div class="welcome-card">
      <h2>直播运营工作台</h2>
      <p>围绕商品资料完成开播准备、实时评论回复和下播复盘</p>
    </div>

    <div class="prep-banner">
      <div class="prep-text">🎯 开播准备：在「商品资料」选中商品后查看资料完整度，缺什么补什么，开播更从容。</div>
      <button class="primary-btn" @click="$emit('navigate', 'products')">去完善商品资料</button>
    </div>

    <h3 class="section-title">运营概览</h3>
    <div class="stats-grid">
      <div v-for="s in STATS" :key="s.label" class="stat-card">
        <div class="stat-icon">{{ s.icon }}</div>
        <div class="stat-label">{{ s.label }}</div>
        <div class="stat-value">{{ stats[s.key] }}</div>
      </div>
    </div>

    <h3 class="section-title">直播流程</h3>
    <div class="quick-grid">
      <div class="quick-card">
        <div class="qc-title">开播前</div>
        <div class="qc-desc">
          <span class="qc-action" @click="$emit('navigate', 'products')">完善商品资料 ›</span>
          <span class="qc-action" @click="$emit('navigate', 'materials')">上传素材资料 ›</span>
          <span class="qc-action" @click="$emit('navigate', 'products')">生成直播话术 ›</span>
        </div>
      </div>
      <div class="quick-card">
        <div class="qc-title">直播中</div>
        <div class="qc-desc">
          <span class="qc-action" @click="$emit('navigate', 'comments')">输入观众评论 ›</span>
          <span class="qc-action" @click="$emit('navigate', 'comments')">生成主播口吻回复 ›</span>
        </div>
      </div>
      <div class="quick-card">
        <div class="qc-title">下播后</div>
        <div class="qc-desc">
          <span class="qc-action" @click="$emit('navigate', 'products')">生成直播复盘 ›</span>
          <span class="qc-action" @click="$emit('navigate', 'products')">查看优化建议 ›</span>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
// 阶段 5.2：运营工作台（以旧页面已有能力为准，不新增业务功能）：
// GET /live-ops/dashboard 优先，失败时回退 GET /dashboard/stats（与旧页面一致）。
// 两个接口都失败时保持默认 0（与旧页面行为一致）。
import { ref, onMounted } from "vue";
import { apiGet } from "../api/client";

defineEmits(["navigate"]);

const stats = ref({
  product_count: 0,
  live_product_count: 0,
  live_script_count: 0,
  comment_reply_count: 0,
  live_review_count: 0,
  knowledge_document_count: 0,
});

const STATS = [
  { icon: "📦", label: "商品资料", key: "product_count" },
  { icon: "🔴", label: "直播中商品", key: "live_product_count" },
  { icon: "✨", label: "已生成话术", key: "live_script_count" },
  { icon: "💬", label: "评论回复", key: "comment_reply_count" },
  { icon: "📊", label: "直播复盘", key: "live_review_count" },
  { icon: "📄", label: "商品资料文档", key: "knowledge_document_count" },
];

async function loadStats() {
  try {
    const s = await apiGet("/live-ops/dashboard");
    stats.value = s;
  } catch (e) {
    try {
      const s = await apiGet("/dashboard/stats");
      stats.value = {
        product_count: s.products,
        live_product_count: s.live_products,
        live_script_count: s.live_scripts,
        comment_reply_count: s.comment_replies,
        live_review_count: s.live_reviews,
        knowledge_document_count: s.knowledge_documents,
      };
    } catch (e2) {
      // 两个接口都失败时保持默认 0（与旧页面一致）
    }
  }
}

onMounted(loadStats);
</script>

<style scoped>
.dashboard-view {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px 20px;
}
.welcome-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 20px 24px;
  margin-bottom: 14px;
}
.welcome-card h2 {
  margin: 0 0 6px;
  font-size: 20px;
}
.welcome-card p {
  margin: 0;
  color: #777;
  font-size: 14px;
}
.prep-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  background: linear-gradient(135deg, #eff6ff, #f0fdf4);
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 14px;
}
.prep-text {
  font-size: 13px;
  color: #777;
  min-width: 0;
}
.primary-btn {
  font-size: 12px;
  padding: 6px 12px;
  flex-shrink: 0;
  border: none;
  border-radius: 6px;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
}
.section-title {
  font-size: 15px;
  font-weight: 700;
  color: #333;
  margin: 18px 0 14px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 14px;
}
.stat-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
  text-align: center;
}
.stat-icon {
  font-size: 22px;
  margin-bottom: 6px;
}
.stat-label {
  color: #777;
  font-size: 12px;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  margin-top: 4px;
}
.quick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 14px;
}
.quick-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}
.qc-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 8px;
}
.qc-desc {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.qc-action {
  font-size: 13px;
  color: #2563eb;
  cursor: pointer;
}
.qc-action:hover {
  text-decoration: underline;
}
</style>
