<template>
  <section class="product-view container">
    <div class="view-head">
      <div>
        <h2 class="view-title">商品资料</h2>
        <p class="view-desc">维护商品基础信息与资料文档，支撑话术生成、评论回复与直播复盘</p>
      </div>
      <div class="view-actions">
        <button class="primary-btn" @click="openCreateForm">
          <Icon name="plus" size="14" /> 新增商品
        </button>
      </div>
    </div>

    <!-- CSV 导入导出：标题区下方的紧凑工具栏，不零散漂浮 -->
    <ProductCsvTools @imported="selectorRef?.reload()" />

    <div class="product-grid">
      <ProductSelector ref="selectorRef" :selected-id="selectedId" @select="onSelect" @create="openCreateForm" />
      <ProductSummary :product="product" :busy="removing" @edit="openEditForm" @remove="onRemoveProduct" />
    </div>

    <h3 class="section-title">商品详情工作区</h3>
    <div class="product-modules">
      <div class="module-wide">
        <PrepSummary :product-id="selectedId" :key="'prep' + refreshTick" />
      </div>
      <ProductCompleteness :product-id="selectedId" :key="'comp' + refreshTick" />
      <ProductDocuments :product-id="selectedId" @changed="refreshTick++" />
      <ProductQa v-if="selectedId" :product-id="selectedId" />
      <ProductQuestionInsights :product-id="selectedId" :key="'ins' + refreshTick" />
      <div class="module-wide">
        <ProductOperationSuggestions :product-id="selectedId" :key="'ops' + refreshTick" />
      </div>
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
// V6 阶段 4：标题区（新增商品归位到右上）、列表/详情双栏（2:3 等高）、
// CSV 工具栏、下方模块统一网格（左右列对齐、无卡片套卡片）。
import { ref } from "vue";
import { apiGet, apiDelete } from "../api/client";
import { toast, confirmDialog } from "../state/feedback";
import Icon from "../components/Icon.vue";
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
  if (!(await confirmDialog("确定要删除这个商品吗？", { danger: true }))) return;
  removing.value = true;
  try {
    await apiDelete(`/products/${selectedId.value}`);
    selectedId.value = null;
    product.value = null;
    selectorRef.value?.reload();
    toast("商品已删除", "success");
  } catch (e) {
    toast(e.message || "删除失败，请稍后重试。", "error");
  } finally {
    removing.value = false;
  }
}
</script>

<style scoped>
/* 商品列表/详情双栏：列表侧 40%、详情主栏 60%，等高（stretch） */
.product-grid {
  display: grid;
  grid-template-columns: minmax(260px, 2fr) minmax(0, 3fr);
  gap: 16px;
  align-items: stretch;
}
/* 分区标题：将下方模块明确归入「商品详情工作区」，减少碎片感 */
.section-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--gray-900);
  margin: 20px 0 14px;
}
/* 下方模块统一网格：左右列对齐，宽模块占满整行 */
.product-modules {
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
  gap: 16px;
  align-items: start;
}
.module-wide {
  grid-column: 1 / -1;
}
@media (max-width: 900px) {
  .product-grid,
  .product-modules {
    grid-template-columns: 1fr;
  }
}
</style>
