<template>
  <div class="modal-overlay" @click.self="cancel">
    <div class="modal-box form-box">
      <div class="modal-head">
        <h3>{{ editProduct ? "编辑商品" : "新增商品" }}</h3>
        <button class="close-btn" @click="cancel"><Icon name="x" size="14" /></button>
      </div>

      <div class="form-field">
        <label for="pf-name">商品名称 *</label>
        <input
          id="pf-name"
          ref="nameInput"
          v-model="form.name"
          placeholder="例如：玻尿酸补水面膜"
          required
          :aria-invalid="Boolean(fieldErrors.name)"
          :aria-describedby="fieldErrors.name ? 'pf-name-error' : undefined"
          @blur="validateField('name')"
          @input="clearFieldError('name')"
        />
        <p v-if="fieldErrors.name" id="pf-name-error" class="field-error" role="alert">
          {{ fieldErrors.name }}
        </p>
      </div>

      <div class="form-row">
        <div class="form-field form-col">
          <label for="pf-price">价格（元） *</label>
          <input
            id="pf-price"
            ref="priceInput"
            v-model="form.price"
            type="text"
            inputmode="decimal"
            placeholder="0.00"
            required
            :aria-invalid="Boolean(fieldErrors.price)"
            :aria-describedby="fieldErrors.price ? 'pf-price-error' : undefined"
            @blur="validateField('price')"
            @input="clearFieldError('price')"
          />
          <p v-if="fieldErrors.price" id="pf-price-error" class="field-error" role="alert">
            {{ fieldErrors.price }}
          </p>
        </div>
        <div class="form-field form-col">
          <label for="pf-stock">库存 *</label>
          <input
            id="pf-stock"
            ref="stockInput"
            v-model="form.stock"
            type="text"
            inputmode="numeric"
            placeholder="0"
            required
            :aria-invalid="Boolean(fieldErrors.stock)"
            :aria-describedby="fieldErrors.stock ? 'pf-stock-error' : undefined"
            @blur="validateField('stock')"
            @input="clearFieldError('stock')"
          />
          <p v-if="fieldErrors.stock" id="pf-stock-error" class="field-error" role="alert">
            {{ fieldErrors.stock }}
          </p>
        </div>
      </div>

      <div class="form-field">
        <label for="pf-selling">核心卖点</label>
        <textarea id="pf-selling" v-model="form.selling_points" placeholder="例如：深层补水、长效保湿" rows="3"></textarea>
      </div>
      <div class="form-field">
        <label for="pf-audience">适用人群</label>
        <input id="pf-audience" v-model="form.target_audience" placeholder="例如：干性皮肤人群" />
      </div>
      <div class="form-field">
        <label for="pf-pain">用户痛点</label>
        <textarea id="pf-pain" v-model="form.pain_points" placeholder="例如：皮肤干燥起皮" rows="3"></textarea>
      </div>
      <div class="form-field">
        <label for="pf-promo">优惠信息</label>
        <input id="pf-promo" v-model="form.promotion" placeholder="例如：买二送一" />
      </div>
      <div class="form-field">
        <label for="pf-status">直播状态</label>
        <select id="pf-status" v-model="form.live_status">
          <option value="未上播">未上播</option>
          <option value="直播中">直播中</option>
          <option value="已下播">已下播</option>
        </select>
      </div>
      <div class="form-field">
        <label for="pf-notes">备注</label>
        <textarea id="pf-notes" v-model="form.notes" placeholder="备注" rows="3"></textarea>
      </div>

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
// 新增 POST /products，编辑 PUT /products/{id}；历史「待上播」数据回填为「未上播」。
// V6：字段容器固定标签/控件排版，并在必要字段下方提供即时校验反馈。
import { nextTick, reactive, ref, watch } from "vue";
import { apiPost, apiPut } from "../api/client";
import { toast } from "../state/feedback";
import Icon from "./Icon.vue";

const props = defineProps({
  editProduct: { type: Object, default: null },
});
const emit = defineEmits(["saved", "close"]);

const VALIDATED_FIELDS = ["name", "price", "stock"];
const fieldErrors = reactive({ name: "", price: "", stock: "" });
const validationToastKey = ref("");
const nameInput = ref(null);
const priceInput = ref(null);
const stockInput = ref(null);
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

function normalizedValue(value) {
  return String(value ?? "").trim();
}

function resetValidation() {
  VALIDATED_FIELDS.forEach((field) => {
    fieldErrors[field] = "";
  });
  validationToastKey.value = "";
}

function clearFieldError(field) {
  fieldErrors[field] = "";
  validationToastKey.value = "";
}

function validateField(field) {
  const value = normalizedValue(form.value[field]);
  let error = "";

  if (field === "name" && !value) {
    error = "请输入商品名称";
  }
  if (field === "price" && (!/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value) || !Number.isFinite(Number(value)))) {
    error = "价格请输入非负金额，例如 0、78、87.50";
  }
  if (field === "stock" && (!/^\d+$/.test(value) || !Number.isFinite(Number(value)))) {
    error = "库存请输入非负整数，例如 0、12、87";
  }

  fieldErrors[field] = error;
  return !error;
}

function validateAll() {
  return VALIDATED_FIELDS.filter((field) => !validateField(field));
}

async function focusFirstInvalid(fields) {
  if (!fields.length) return;
  await nextTick();
  const inputs = { name: nameInput, price: priceInput, stock: stockInput };
  inputs[fields[0]].value?.focus();
}

watch(
  () => props.editProduct,
  (p) => {
    resetValidation();
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

  const invalidFields = validateAll();
  if (invalidFields.length) {
    const errorKey = invalidFields.join(",");
    if (validationToastKey.value !== errorKey) {
      toast("请检查表单中的错误项", "error");
      validationToastKey.value = errorKey;
    }
    await focusFirstInvalid(invalidFields);
    return;
  }

  validationToastKey.value = "";
  const data = {
    name: normalizedValue(form.value.name),
    price: Number(normalizedValue(form.value.price)),
    stock: Number(normalizedValue(form.value.stock)),
    selling_points: normalizedValue(form.value.selling_points),
    target_audience: normalizedValue(form.value.target_audience),
    pain_points: normalizedValue(form.value.pain_points),
    promotion: normalizedValue(form.value.promotion),
    live_status: form.value.live_status || "未上播",
    notes: normalizedValue(form.value.notes),
  };

  saving.value = true;
  try {
    const saved = props.editProduct
      ? await apiPut(`/products/${props.editProduct.id}`, data)
      : await apiPost("/products", data);
    emit("saved", saved);
  } catch (e) {
    toast(e.message || "保存失败，请稍后重试。", "error");
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.form-box {
  width: min(600px, calc(100vw - 32px));
}
.form-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}
.form-field label {
  display: block;
  margin: 0;
}
.form-field input,
.form-field select,
.form-field textarea {
  margin: 0;
}
.form-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}
.form-row .form-field {
  margin-bottom: 0;
}
.field-error {
  margin: 0;
  color: var(--danger);
  font-size: var(--text-xs);
  line-height: 1.4;
}
.form-field input[aria-invalid="true"],
.form-field select[aria-invalid="true"],
.form-field textarea[aria-invalid="true"] {
  border-color: var(--danger);
}
.form-field input[aria-invalid="true"]:focus,
.form-field select[aria-invalid="true"]:focus,
.form-field textarea[aria-invalid="true"]:focus {
  border-color: var(--danger);
  box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.15);
}
textarea {
  min-height: 60px;
}
.form-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
</style>
