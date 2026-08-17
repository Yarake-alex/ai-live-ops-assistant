<template>
  <div class="modal-overlay" @click.self="cancel">
    <div class="modal-box form-box">
      <div class="modal-head">
        <h3>{{ editProduct ? "编辑商品" : "新增商品" }}</h3>
        <button class="close-btn" @click="cancel"><Icon name="x" size="14" /></button>
      </div>

      <label for="pf-name">商品名称 *</label>
      <input id="pf-name" v-model="form.name" placeholder="例如：玻尿酸补水面膜" />
      <div class="form-row">
        <div class="form-col">
          <label for="pf-price">价格（元）</label>
          <input id="pf-price" v-model="form.price" type="number" step="0.01" min="0" placeholder="0.00" />
        </div>
        <div class="form-col">
          <label for="pf-stock">库存</label>
          <input id="pf-stock" v-model="form.stock" type="number" step="1" min="0" placeholder="0" />
        </div>
      </div>
      <label for="pf-selling">核心卖点</label>
      <textarea id="pf-selling" v-model="form.selling_points" placeholder="例如：深层补水、长效保湿" rows="3"></textarea>
      <label for="pf-audience">适用人群</label>
      <input id="pf-audience" v-model="form.target_audience" placeholder="例如：干性皮肤人群" />
      <label for="pf-pain">用户痛点</label>
      <textarea id="pf-pain" v-model="form.pain_points" placeholder="例如：皮肤干燥起皮" rows="3"></textarea>
      <label for="pf-promo">优惠信息</label>
      <input id="pf-promo" v-model="form.promotion" placeholder="例如：买二送一" />
      <label for="pf-status">直播状态</label>
      <select id="pf-status" v-model="form.live_status">
        <option value="未上播">未上播</option>
        <option value="直播中">直播中</option>
        <option value="已下播">已下播</option>
      </select>
      <label for="pf-notes">备注</label>
      <textarea id="pf-notes" v-model="form.notes" placeholder="备注" rows="3"></textarea>

      <div class="form-actions">
        <button class="primary-btn" :disabled="saving" @click="save">
          {{ saving ? "保存中..." : "保存" }}
        </button>
        <button class="light-btn" :disabled="saving" @click="cancel">取消</button>
      </div>
    </div>
  </div>
</template>

<script setup>
// 阶段 5.3a：商品新增/编辑表单（与旧页面一致）：
// 新增 POST /products，编辑 PUT /products/{id}；校验文案与旧页面一致。
// 历史「待上播」数据回填时映射为「未上播」（下拉中已无该选项）。
// V6：统一弹窗样式 + 表单 label 分组。
import { ref, watch } from "vue";
import { apiPost, apiPut } from "../api/client";
import Icon from "./Icon.vue";

const props = defineProps({
  editProduct: { type: Object, default: null },
});
const emit = defineEmits(["saved", "close"]);

const saving = ref(false);
const form = ref(emptyForm());

function emptyForm() {
  return {
    name: "",
    price: "",
    stock: "",
    selling_points: "",
    target_audience: "",
    pain_points: "",
    promotion: "",
    live_status: "未上播",
    notes: "",
  };
}

function fillFromProduct(p) {
  form.value = {
    name: p.name || "",
    price: p.price ?? "",
    stock: p.stock ?? "",
    selling_points: p.selling_points || "",
    target_audience: p.target_audience || "",
    pain_points: p.pain_points || "",
    promotion: p.promotion || "",
    live_status: p.live_status && p.live_status !== "待上播" ? p.live_status : "未上播",
    notes: p.notes || "",
  };
}

watch(
  () => props.editProduct,
  (p) => {
    if (p) {
      fillFromProduct(p);
    } else {
      form.value = emptyForm();
    }
  },
  { immediate: true }
);

function cancel() {
  if (saving.value) return;
  emit("close");
}

async function save() {
  if (saving.value) return;
  const data = {
    name: form.value.name.trim(),
    price: form.value.price === "" ? 0 : Number(form.value.price),
    stock: form.value.stock === "" ? 0 : Number(form.value.stock),
    selling_points: form.value.selling_points.trim(),
    target_audience: form.value.target_audience.trim(),
    pain_points: form.value.pain_points.trim(),
    promotion: form.value.promotion.trim(),
    live_status: form.value.live_status || "未上播",
    notes: form.value.notes.trim(),
  };

  if (!data.name) {
    alert("商品名称必填");
    return;
  }
  if (Number.isNaN(data.price) || data.price < 0) {
    alert("价格不能为负数");
    return;
  }
  if (Number.isNaN(data.stock) || data.stock < 0 || !Number.isInteger(data.stock)) {
    alert("库存必须是非负整数");
    return;
  }

  saving.value = true;
  try {
    const saved = props.editProduct
      ? await apiPut(`/products/${props.editProduct.id}`, data)
      : await apiPost("/products", data);
    emit("saved", saved);
  } catch (e) {
    alert(e.message || "保存失败，请稍后重试。");
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.form-box {
  width: min(600px, calc(100vw - 32px));
}
.form-box input,
.form-box select,
.form-box textarea {
  margin-bottom: 8px;
}
.form-box label {
  margin-bottom: 4px;
}
textarea {
  min-height: 60px;
}
.form-row {
  display: flex;
  gap: 8px;
}
.form-col {
  flex: 1;
  min-width: 0;
}
.form-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
</style>
