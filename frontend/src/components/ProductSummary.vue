<template>
  <div class="product-summary">
    <div v-if="!product" class="summary-empty">
      <div class="empty-icon">📦</div>
      <div>请选择一个商品以查看详情</div>
    </div>
    <template v-else>
      <div class="summary-name-row">
        <div class="summary-name">{{ product.name }}</div>
        <div class="summary-actions">
          <button class="edit-btn" :disabled="busy" @click="$emit('edit')">✏️ 编辑商品</button>
          <button class="delete-btn" :disabled="busy" @click="$emit('remove')">🗑 删除商品</button>
        </div>
      </div>
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
// 阶段 4.1 + 5.3a：当前商品基础信息展示 + 编辑入口（与旧页面文案一致）。
// 删除等操作按钮留待后续阶段迁移。
defineProps({
  product: { type: Object, default: null },
  busy: Boolean,
});
defineEmits(["edit", "remove"]);
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
.summary-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.summary-name {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 4px;
}
.summary-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.edit-btn {
  font-size: 12px;
  padding: 4px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
  color: #555;
  cursor: pointer;
}
.edit-btn:hover {
  background: #f9fafb;
}
.delete-btn {
  font-size: 12px;
  padding: 4px 10px;
  border: none;
  border-radius: 6px;
  background: #dc2626;
  color: #fff;
  cursor: pointer;
}
.edit-btn:disabled,
.delete-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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
