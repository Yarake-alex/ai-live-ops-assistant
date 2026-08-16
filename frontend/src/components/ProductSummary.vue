<template>
  <div class="product-summary">
    <div v-if="!product" class="summary-empty">
      <div class="empty-icon">📦</div>
      <div>请选择一个商品以查看详情</div>
    </div>
    <template v-else>
      <div class="summary-name">{{ product.name }}</div>
      <div class="summary-sub">💰 ¥{{ product.price }} · 库存 {{ product.stock }}</div>
      <div class="summary-tags">
        <span class="status-tag">{{ product.live_status || "未上播" }}</span>
        <span v-if="product.promotion" class="promo-tag">🎁 {{ product.promotion }}</span>
      </div>
      <div class="summary-fields">
        <div>✨ 核心卖点：{{ product.selling_points || "未填写" }}</div>
        <div>👥 适用人群：{{ product.target_audience || "未填写" }}</div>
        <div>⚠️ 用户痛点：{{ product.pain_points || "未填写" }}</div>
        <div class="summary-notes">📝 {{ product.notes || "无备注" }}</div>
      </div>
    </template>
  </div>
</template>

<script setup>
// 阶段 4.1：当前商品基础信息展示（与旧页面文案一致）。
// 编辑/删除等操作按钮留待后续阶段迁移。
defineProps({
  product: { type: Object, default: null },
});
</script>

<style scoped>
.product-summary {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  padding: 20px;
  min-height: 200px;
}
.summary-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 200px;
  color: #999;
  font-size: 14px;
}
.empty-icon {
  font-size: 40px;
}
.summary-name {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 4px;
}
.summary-sub {
  color: #777;
  margin-bottom: 12px;
}
.summary-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.status-tag {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #555;
}
.promo-tag {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 999px;
  background: #fef3c7;
  color: #92400e;
}
.summary-fields {
  line-height: 2;
  font-size: 14px;
  color: #555;
}
.summary-notes {
  margin-top: 8px;
  padding: 8px;
  background: #f8fafc;
  border-radius: 6px;
}
</style>
