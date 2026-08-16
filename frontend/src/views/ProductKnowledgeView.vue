<template>
  <section class="product-view">
    <div class="product-grid">
      <ProductSelector ref="selectorRef" :selected-id="selectedId" @select="onSelect" @create="openCreateForm" />
      <ProductSummary :product="product" @edit="openEditForm" />
    </div>
    <div class="product-modules">
      <ProductCompleteness :product-id="selectedId" />
      <ProductDocuments :product-id="selectedId" />
      <ProductQa v-if="selectedId" :product-id="selectedId" />
      <ProductQuestionInsights :product-id="selectedId" />
      <ProductOperationSuggestions :product-id="selectedId" />
      <ProductLiveScript :product-id="selectedId" />
      <ProductLiveReview :product-id="selectedId" />
    </div>

    <ProductForm
      v-if="formOpen"
      :edit-product="editingProduct"
      @saved="onProductSaved"
      @close="formOpen = false"
    />
  </section>
</template>

<script setup>
// 阶段 4.1-4.7：迁移商品资料页的「商品选择 + 当前商品基础信息 +
// 资料完整度 + 资料文档列表 + 资料问答（本地快答/知识库问答）+ 问题洞察 +
// 运营建议 + 直播话术 + 直播复盘」。
// 接口与旧页面完全一致：GET /products/search、GET /products/{id}、
// GET /products/{id}/readiness、GET /products/{id}/knowledge/documents、
// POST /products/{id}/knowledge/ask、GET /products/{id}/question-insights、
// GET /products/{id}/ops-suggestions、POST /products/{id}/live-scripts、
// GET /products/{id}/live-scripts、GET /live-scripts/{id}、
// POST /products/{id}/live-reviews、GET /products/{id}/live-reviews、
// GET /live-reviews/{id}，返回结构不变。
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
import ProductLiveReview from "../components/ProductLiveReview.vue";
import ProductForm from "../components/ProductForm.vue";

const selectedId = ref(null);
const product = ref(null);
const selectorRef = ref(null);
const formOpen = ref(false);
const editingProduct = ref(null);

async function onSelect(id) {
  selectedId.value = id;
  try {
    product.value = await apiGet(`/products/${id}`);
  } catch (e) {
    product.value = null;
  }
}

function openCreateForm() {
  editingProduct.value = null;
  formOpen.value = true;
}

function openEditForm() {
  if (!product.value) return;
  editingProduct.value = product.value;
  formOpen.value = true;
}

// 保存后：关闭表单、刷新列表；若编辑的是当前选中商品，重新拉取详情（与旧页面一致）
function onProductSaved(saved) {
  formOpen.value = false;
  editingProduct.value = null;
  selectorRef.value?.reload();
  if (saved && saved.id === selectedId.value) {
    onSelect(saved.id);
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
