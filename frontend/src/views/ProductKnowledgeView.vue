<template>
  <section class="product-view">
    <div class="view-head">
      <h2>商品资料</h2>
    </div>
    <ProductCsvTools @imported="selectorRef?.reload()" />
    <div class="product-grid">
      <ProductSelector ref="selectorRef" :selected-id="selectedId" @select="onSelect" @create="openCreateForm" />
      <ProductSummary :product="product" :busy="removing" @edit="openEditForm" @remove="onRemoveProduct" />
    </div>
    <div class="product-modules">
      <PrepSummary :product-id="selectedId" :key="'prep' + refreshTick" />
      <ProductCompleteness :product-id="selectedId" :key="'comp' + refreshTick" />
      <ProductDocuments :product-id="selectedId" @changed="refreshTick++" />
      <ProductQa v-if="selectedId" :product-id="selectedId" />
      <ProductQuestionInsights :product-id="selectedId" :key="'ins' + refreshTick" />
      <ProductOperationSuggestions :product-id="selectedId" :key="'ops' + refreshTick" />
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
import { apiGet, apiDelete } from "../api/client";
import ProductSelector from "../components/ProductSelector.vue";
import ProductSummary from "../components/ProductSummary.vue";
import ProductCompleteness from "../components/ProductCompleteness.vue";
import ProductDocuments from "../components/ProductDocuments.vue";
import PrepSummary from "../components/PrepSummary.vue";
import ProductQa from "../components/ProductQa.vue";
import ProductQuestionInsights from "../components/ProductQuestionInsights.vue";
import ProductOperationSuggestions from "../components/ProductOperationSuggestions.vue";
import ProductLiveScript from "../components/ProductLiveScript.vue";
import ProductLiveReview from "../components/ProductLiveReview.vue";
import ProductForm from "../components/ProductForm.vue";
import ProductCsvTools from "../components/ProductCsvTools.vue";

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

// 删除商品：确认 → 删除 → 清空选中状态 → 刷新列表（与旧页面一致）
const removing = ref(false);

// 资料文档上传/删除/整理后，用 key 重挂载联动刷新完整度/概览/洞察/运营建议
const refreshTick = ref(0);

async function onRemoveProduct() {
  if (!selectedId.value || removing.value) return;
  if (!confirm("确定要删除这个商品吗？")) return;
  removing.value = true;
  try {
    await apiDelete(`/products/${selectedId.value}`);
    selectedId.value = null;
    product.value = null;
    selectorRef.value?.reload();
    alert("商品已删除");
  } catch (e) {
    alert(e.message || "删除失败，请稍后重试。");
  } finally {
    removing.value = false;
  }
}
</script>

<style scoped>
.product-view {
  max-width: var(--content-max);
  margin: 0 auto;
  padding: 24px 20px;
}
.view-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}
.view-head h2 {
  margin: 0;
  font-size: 18px;
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
