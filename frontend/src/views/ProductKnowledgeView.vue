<template>
  <section class="product-view">
    <div class="product-grid">
      <ProductSelector :selected-id="selectedId" @select="onSelect" />
      <ProductSummary :product="product" />
    </div>
    <div class="product-modules">
      <ProductCompleteness :product-id="selectedId" />
      <ProductDocuments :product-id="selectedId" />
      <ProductQa v-if="selectedId" :product-id="selectedId" />
      <ProductQuestionInsights :product-id="selectedId" />
      <ProductOperationSuggestions :product-id="selectedId" />
      <ProductLiveScript :product-id="selectedId" />
    </div>
  </section>
</template>

<script setup>
// 阶段 4.1-4.6：迁移商品资料页的「商品选择 + 当前商品基础信息 +
// 资料完整度 + 资料文档列表 + 资料问答（本地快答/知识库问答）+ 问题洞察 +
// 运营建议 + 直播话术」。
// 接口与旧页面完全一致：GET /products/search、GET /products/{id}、
// GET /products/{id}/readiness、GET /products/{id}/knowledge/documents、
// POST /products/{id}/knowledge/ask、GET /products/{id}/question-insights、
// GET /products/{id}/ops-suggestions、POST /products/{id}/live-scripts、
// GET /products/{id}/live-scripts、GET /live-scripts/{id}，返回结构不变。
// 复盘等留待后续阶段。
import { ref } from "vue";
import { apiGet } from "../api/client";
import ProductSelector from "../components/ProductSelector.vue";
import ProductSummary from "../components/ProductSummary.vue";
import ProductCompleteness from "../components/ProductCompleteness.vue";
import ProductDocuments from "../components/ProductDocuments.vue";
import ProductQa from "../components/ProductQa.vue";
import ProductQuestionInsights from "../components/ProductQuestionInsights.vue";
import ProductOperationSuggestions from "../components/ProductOperationSuggestions.vue";
import ProductLiveScript from "../components/ProductLiveScript.vue";

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
