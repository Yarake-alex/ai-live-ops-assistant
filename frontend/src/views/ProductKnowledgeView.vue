<template>
  <section class="product-view">
    <div class="product-grid">
      <ProductSelector :selected-id="selectedId" @select="onSelect" />
      <ProductSummary :product="product" />
    </div>
  </section>
</template>

<script setup>
// 阶段 4.1：迁移商品资料页的「商品选择 + 当前商品基础信息」。
// 接口与旧页面完全一致：GET /products/search、GET /products/{id}，返回结构不变。
// 资料完整度、资料文档、资料问答、问题洞察、运营建议、话术、复盘等留待后续阶段。
import { ref } from "vue";
import { apiGet } from "../api/client";
import ProductSelector from "../components/ProductSelector.vue";
import ProductSummary from "../components/ProductSummary.vue";

const selectedId = ref(null);
const product = ref(null);

async function onSelect(id) {
  selectedId.value = id;
  try {
    product.value = await apiGet(`/products/${id}`);
  } catch (e) {
    product.value = null;
  }
}
</script>

<style scoped>
.product-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 20px;
}
.product-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  align-items: start;
}
@media (max-width: 900px) {
  .product-grid {
    grid-template-columns: 1fr;
  }
}
</style>
