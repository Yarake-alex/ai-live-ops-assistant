<template>
  <section class="comment-view container">
    <div class="view-head">
      <div>
        <h2 class="view-title">评论助手</h2>
        <p class="view-desc">输入观众评论，生成主播口吻回复，并回看历史记录</p>
      </div>
    </div>

    <div class="comment-grid">
      <!-- Left: Comment input + result (main, 60%) -->
      <div class="card">
        <div class="card-head">
          <h3><Icon name="chat" size="15" class="head-icon" /> 模拟评论</h3>
        </div>
        <label for="cm-product">选择商品</label>
        <select id="cm-product" v-model="productId" @change="onProductChange">
          <option value="">请选择商品…</option>
          <option v-for="p in products" :key="p.id" :value="String(p.id)">{{ p.name }}</option>
        </select>
        <label for="cm-comment">观众评论</label>
        <textarea
          id="cm-comment"
          v-model="comment"
          placeholder="输入观众评论，例如：多少钱？"
          rows="4"
          :disabled="generating"
        ></textarea>
        <div class="quick-row">
          <button
            v-for="example in EXAMPLES"
            :key="example"
            class="preset-btn"
            :disabled="generating"
            @click="comment = example"
          >
            {{ example }}
          </button>
        </div>
        <div class="actions-row">
          <button class="primary-btn" :disabled="generating" @click="generate">
            <Icon name="mic" size="14" /> 生成回复
          </button>
        </div>
        <div class="result-box">
          <div v-if="generating" class="hint">AI 正在生成回复...</div>
          <div v-else-if="generateError" class="hint hint-error">生成失败，请稍后重试。</div>
          <div v-else-if="!record" class="empty">
            <span class="empty-icon"><Icon name="chat" size="24" /></span>
            <span>生成的直播间回复会显示在这里。</span>
          </div>
          <template v-else>
            <div class="record-meta">
              <span class="tag" :class="statusTagClass(record)">{{ statusText(record) }}</span>
            </div>
            <div class="muted record-comment">观众评论：{{ record.comment }}</div>
            <div v-if="record.status !== 'success' && record.error_message" class="muted record-warning">
              {{ record.error_message }}
            </div>
            <div class="record-reply">{{ record.reply }}</div>
          </template>
        </div>
      </div>

      <!-- Right: History (side, 40%) -->
      <div class="card">
        <div class="card-head">
          <h3>历史评论与回复</h3>
          <button class="light-btn" :disabled="historyLoading" @click="loadHistory">刷新</button>
        </div>
        <div class="history-box">
          <div v-if="historyLoading" class="hint">加载中…</div>
          <div v-else-if="historyError" class="hint hint-error">历史记录加载失败。</div>
          <div v-else-if="!productId" class="empty">
            <span class="empty-icon"><Icon name="chat" size="24" /></span>
            <span>选择商品后显示该商品的历史评论回复。</span>
          </div>
          <div v-else-if="!history.length" class="empty">
            <span class="empty-icon"><Icon name="chat" size="24" /></span>
            <span>暂无历史评论回复。</span>
          </div>
          <div
            v-for="item in history"
            :key="item.id"
            class="row-item history-item"
            :class="{ active: item.id === viewedId }"
          >
            <div class="history-top">
              <b>{{ (item.comment || "").slice(0, 40) }}</b>
              <span class="tag" :class="statusTagClass(item)">{{ statusText(item) }}</span>
            </div>
            <div class="muted history-reply">{{ (item.reply || "（无回复内容）").slice(0, 60) }}</div>
            <div class="history-bottom">
              <span class="muted">{{ createdText(item) }}</span>
              <button class="light-btn" @click="viewDetail(item.id)">查看</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
// 阶段 5.2：评论助手（与旧页面文案一致）：
// GET /products 商品下拉、POST /products/{id}/comment-replies 生成回复、
// GET /products/{id}/comment-replies 历史列表、GET /comment-replies/{id} 查看详情。
// V6 阶段 5：稳定双栏（主栏 60% 输入+结果 / 侧栏 40% 历史）；
// 预设问题改紧凑 tag；结果与历史加状态 badge；历史「查看」当前项高亮。
import { ref, onMounted } from "vue";
import { apiGet, apiPost } from "../api/client";
import { toast } from "../state/feedback";
import Icon from "../components/Icon.vue";

const EXAMPLES = ["多少钱？", "适合学生吗？", "有没有优惠？", "质量怎么样？", "敏感肌能用吗？"];

const products = ref([]);
const productId = ref("");
const comment = ref("");
const generating = ref(false);
const generateError = ref(false);
const record = ref(null);

const historyLoading = ref(false);
const historyError = ref(false);
const history = ref([]);
const viewedId = ref(null);

function statusText(r) {
  if (r.status === "fallback") return "本地兜底";
  if (r.status === "failed") return "生成失败";
  return "生成成功";
}

function statusTagClass(r) {
  if (r.status === "fallback") return "tag-warning";
  if (r.status === "failed") return "tag-danger";
  return "tag-success";
}

function createdText(r) {
  return r.created_at ? new Date(r.created_at).toLocaleString() : "";
}

async function loadProducts() {
  try {
    const data = await apiGet("/products");
    const prev = productId.value;
    products.value = data || [];
    if (prev && products.value.some((p) => String(p.id) === prev)) {
      productId.value = prev;
    } else {
      productId.value = "";
      record.value = null;
      history.value = [];
    }
  } catch (e) {
    products.value = [];
  }
}

function onProductChange() {
  record.value = null;
  generateError.value = false;
  history.value = [];
  viewedId.value = null;
  if (productId.value) {
    loadHistory();
  }
}

async function generate() {
  if (!productId.value) {
    toast("请先选择商品", "error");
    return;
  }
  const text = comment.value.trim();
  if (!text) {
    toast("请输入评论内容", "error");
    return;
  }
  generating.value = true;
  generateError.value = false;
  try {
    const data = await apiPost(`/products/${productId.value}/comment-replies`, { comment: text });
    record.value = data;
    viewedId.value = null;
    await loadHistory();
  } catch (e) {
    generateError.value = true;
    record.value = null;
  } finally {
    generating.value = false;
  }
}

async function loadHistory() {
  if (!productId.value) return;
  historyLoading.value = true;
  historyError.value = false;
  try {
    history.value = await apiGet(`/products/${productId.value}/comment-replies`);
  } catch (e) {
    historyError.value = true;
    history.value = [];
  } finally {
    historyLoading.value = false;
  }
}

async function viewDetail(id) {
  try {
    const data = await apiGet(`/comment-replies/${id}`);
    record.value = data;
    viewedId.value = id;
  } catch (e) {
    // 忽略，保持原展示
  }
}

onMounted(loadProducts);
</script>

<style scoped>
/* 稳定双栏：主栏（输入+结果）60%，侧栏（历史）40%；窄屏自动堆叠 */
.comment-grid {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  gap: 16px;
  align-items: stretch;
}
@media (max-width: 900px) {
  .comment-grid {
    grid-template-columns: 1fr;
  }
}
select,
textarea {
  margin-bottom: 8px;
}
textarea {
  min-height: 100px;
}
.quick-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
/* 预设问题：紧凑可点击 tag（热区 ≥30px），不挤压文本域 */
.preset-btn {
  min-height: 30px;
  padding: 4px 12px;
  font-size: 13px;
  background: var(--panel-bg);
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-pill);
  color: var(--gray-600);
}
.preset-btn:hover:not(:disabled) {
  border-color: var(--primary-border);
  color: var(--primary);
  background: var(--primary-soft);
}
.actions-row {
  margin-bottom: 10px;
}
.comment-view .empty {
  padding: 16px;
}
.record-meta {
  margin-bottom: 8px;
}
.record-comment {
  font-size: 13px;
  margin-bottom: 8px;
}
.record-warning {
  margin-bottom: 8px;
}
.record-reply {
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-all;
}
.history-box {
  max-height: 60vh;
  overflow-y: auto;
}
.history-item {
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
}
.history-item.active {
  background: var(--primary-soft);
  border-radius: var(--radius-sm);
  padding-left: 8px;
  padding-right: 8px;
}
.history-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.history-top b {
  font-size: 13px;
}
.history-reply {
  margin-top: 4px;
}
.history-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}
</style>
