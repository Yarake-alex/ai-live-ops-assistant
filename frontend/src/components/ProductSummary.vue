<template>
  <div class="product-summary">
    <div class="card-head">
      <h3>商品详情</h3>
      <div v-if="product" class="summary-actions">
        <button class="light-btn" :disabled="busy" @click="$emit('edit')">
          <Icon name="edit" size="13" /> 编辑商品
        </button>
        <button class="danger-btn" :disabled="busy" @click="$emit('remove')">
          <Icon name="trash" size="13" /> 删除商品
        </button>
      </div>
    </div>

    <div v-if="!product" class="empty">
      <span class="empty-icon"><Icon name="box" size="32" /></span>
      <span>请选择一个商品以查看详情</span>
    </div>
    <template v-else>
      <div class="summary-name">{{ product.name }}</div>
      <div class="summary-sub">¥{{ product.price }} · 库存 {{ product.stock }}</div>
      <div class="summary-tags">
        <span class="status-tag">{{ product.live_status || "未上播" }}</span>
        <span v-if="product.promotion" class="promo-tag">{{ product.promotion }}</span>
      </div>
      <div class="summary-fields">
        <div class="field-row">
          <span class="field-label">核心卖点</span>
          <span class="field-value">{{ product.selling_points || "未填写" }}</span>
        </div>
        <div class="field-row">
          <span class="field-label">适用人群</span>
          <span class="field-value">{{ product.target_audience || "未填写" }}</span>
        </div>
        <div class="field-row">
          <span class="field-label">用户痛点</span>
          <span class="field-value">{{ product.pain_points || "未填写" }}</span>
        </div>
        <div class="field-row">
          <span class="field-label">备注</span>
          <span class="field-value">{{ product.notes || "无备注" }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
// 阶段 4.1 + 5.3a：当前商品基础信息展示 + 编辑入口（与旧页面文案一致）。
// V6 阶段 4：标题区/操作区结构统一；卖点/人群/痛点用键值行；空态统一。
import Icon from "./Icon.vue";

defineProps({
  product: { type: Object, default: null },
  busy: Boolean,
});
defineEmits(["edit", "remove"]);
</script>

<style scoped>
.product-summary {
  min-height: 200px;
  display: flex;
  flex-direction: column;
}
.product-summary .empty {
  flex: 1;
}
.summary-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.summary-name {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 4px;
}
.summary-sub {
  color: var(--gray-500);
  font-size: 13px;
  margin-bottom: 12px;
}
.summary-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.summary-fields {
  border-top: 1px solid var(--gray-100);
  padding-top: 4px;
}
.field-row {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--gray-100);
  font-size: 13px;
  line-height: 1.7;
}
.field-row:last-child {
  border-bottom: none;
}
.field-label {
  flex-shrink: 0;
  width: 64px;
  color: var(--gray-500);
}
.field-value {
  flex: 1;
  min-width: 0;
  color: var(--gray-700);
  word-break: break-all;
}
</style>
