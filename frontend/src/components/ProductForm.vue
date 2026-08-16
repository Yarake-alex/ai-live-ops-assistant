<template>
  <div class="form-overlay" @click.self="cancel">
    <div class="form-box">
      <div class="form-head">
        <h3>{{ editProduct ? "编辑商品" : "新增商品" }}</h3>
        <button class="close-btn" @click="cancel">✕</button>
      </div>

      <input v-model="form.name" placeholder="商品名称 *" />
      <div class="form-row">
        <input v-model="form.price" type="number" step="0.01" min="0" placeholder="价格（元）" />
        <input v-model="form.stock" type="number" step="1" min="0" placeholder="库存" />
      </div>
      <textarea v-model="form.selling_points" placeholder="核心卖点，例如：深层补水、长效保湿" rows="3"></textarea>
      <input v-model="form.target_audience" placeholder="适用人群，例如：干性皮肤人群" />
      <textarea v-model="form.pain_points" placeholder="用户痛点，例如：皮肤干燥起皮" rows="3"></textarea>
      <input v-model="form.promotion" placeholder="优惠信息，例如：买二送一" />
      <select v-model="form.live_status">
        <option value="未上播">未上播</option>
        <option value="直播中">直播中</option>
        <option value="已下播">已下播</option>
      </select>
      <textarea v-model="form.notes" placeholder="备注" rows="3"></textarea>

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
import { ref, watch } from "vue";
import { apiPost, apiPut } from "../api/client";

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
.form-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.form-box {
  width: min(600px, calc(100vw - 32px));
  max-height: 85vh;
  overflow-y: auto;
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
}
.form-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.form-head h3 {
  margin: 0;
  font-size: 15px;
}
.close-btn {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 14px;
  color: #777;
}
input,
select,
textarea {
  width: 100%;
  font-size: 13px;
  margin-bottom: 8px;
}
textarea {
  min-height: 60px;
}
.form-row {
  display: flex;
  gap: 8px;
}
.form-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.primary-btn {
  padding: 6px 16px;
  font-size: 13px;
  border: none;
  border-radius: 6px;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
}
.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.light-btn {
  padding: 6px 14px;
  font-size: 13px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
  color: #555;
  cursor: pointer;
}
.light-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
