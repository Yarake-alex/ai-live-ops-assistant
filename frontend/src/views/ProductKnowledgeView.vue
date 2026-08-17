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

    <!-- 商品运营工作区：仅在选中商品后渲染；Tab 切换，按访问加载 -->
    <template v-if="selectedId">
      <div class="workspace-head">
        <h3 class="section-title">商品运营工作区</h3>
        <!-- 当前商品的四项轻量状态摘要：复用既有聚合加载逻辑，不新增接口 -->
        <PrepSummary :product-id="selectedId" :key="'prep' + refreshTick" @docs="docsCount = $event" />
      </div>
      <div class="ops-tabs" role="tablist" aria-label="商品运营工作区">
        <button
          v-for="t in TABS"
          :key="t.key"
          class="ops-tab"
          role="tab"
          :aria-selected="activeTab === t.key"
          :class="{ active: activeTab === t.key }"
          @click="activeTab = t.key"
        >
          {{ t.label }}
        </button>
      </div>
      <div class="ops-tab-panel" role="tabpanel">
        <!-- 资料与完整度：单一横向全宽主面板，文档为主内容 -->
        <div v-if="activeTab === 'materials'" class="card materials-panel">
          <div class="card-head">
            <h3><Icon name="file" size="15" class="head-icon" /> 补充商品资料</h3>
          </div>
          <!-- 完整度详情只提供缺失项/下一步建议，避免重复头部百分比摘要。 -->
          <ProductCompleteness :product-id="selectedId" :key="'comp' + refreshTick" compact />
          <ProductDocuments
            :product-id="selectedId"
            @changed="refreshTick++"
            @docs="docsCount = $event"
          />
        </div>

        <!-- 智能问答：资料问答 + 问题洞察 -->
        <div v-else-if="activeTab === 'qa'" class="tab-split">
          <ProductQa :product-id="selectedId" />
          <ProductQuestionInsights :product-id="selectedId" :key="'ins' + refreshTick" />
        </div>

        <ProductOperationSuggestions
          v-else-if="activeTab === 'suggestions'"
          :product-id="selectedId"
          :key="'ops' + refreshTick"
        />

        <ProductLiveScript
          v-else-if="activeTab === 'script'"
          :product-id="selectedId"
          :disable-hint="docsCount === 0 ? '生成直播话术需要商品资料：请先在「资料与完整度」上传资料文档。' : ''"
        />

        <ProductLiveReview v-else :product-id="selectedId" />
      </div>
    </template>

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
// V6 信息架构收紧：未选中商品时不渲染运营工作区；选中后 Tab 切换（按访问加载），
// 默认「资料与完整度」；切换商品回到默认 Tab。
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

const TABS = [
  { key: "materials", label: "资料与完整度" },
  { key: "qa", label: "智能问答" },
  { key: "suggestions", label: "运营建议" },
  { key: "script", label: "直播话术" },
  { key: "review", label: "直播复盘" },
];

const selectedId = ref(null);
const product = ref(null);
const selectorRef = ref(null);
const formOpen = ref(false);
const editingProduct = ref(null);
const activeTab = ref("materials");
// 当前商品资料文档数（由 ProductDocuments 上报）：0 时话术生成前置条件不足
const docsCount = ref(null);

async function onSelect(id) {
  selectedId.value = id;
  activeTab.value = "materials";
  docsCount.value = null;
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
    docsCount.value = null;
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
.workspace-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin: 20px 0 14px;
}
.workspace-head .section-title {
  margin: 0;
}
/* 运营工作区 Tab 条：选中态深色文字 + 2px 蓝色底边 */
.ops-tabs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--gray-200);
  margin-bottom: 16px;
}
.ops-tab {
  min-height: 38px;
  padding: 0 14px;
  border: none;
  border-radius: 0;
  background: transparent;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  color: var(--gray-600);
  white-space: nowrap;
}
.ops-tab:hover:not(:disabled) {
  color: var(--gray-900);
  background: var(--gray-50);
}
.ops-tab.active {
  color: var(--gray-900);
  font-weight: 600;
  border-bottom-color: var(--primary);
}
/* 资料 Tab：一个全宽主面板；文档区占据全部有效宽度。 */
.materials-panel :deep(.module-section) + :deep(.module-section) {
  border-top: 1px solid var(--gray-100);
  margin-top: 14px;
  padding-top: 14px;
}
/* 智能问答 Tab 仍保留双栏，仅在该 Tab 内生效。 */
.tab-split {
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
  gap: 0 24px;
  align-items: start;
}
@media (max-width: 900px) {
  .product-grid,
  .tab-split {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 768px) {
  .workspace-head {
    align-items: flex-start;
  }
}
</style>
