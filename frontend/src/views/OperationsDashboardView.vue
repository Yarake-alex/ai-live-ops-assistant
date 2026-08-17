<template>
  <section class="dashboard-view container">
    <div class="view-head">
      <div>
        <h2 class="view-title">运营工作台</h2>
        <p class="view-desc">围绕商品资料完成开播准备、实时评论回复和下播复盘</p>
      </div>
    </div>

    <!-- 三步任务引导（跳转不变） -->
    <div class="steps-row">
      <button class="step" @click="$emit('navigate', 'products')">
        <span class="step-num">1</span>
        <span class="step-text">完善商品资料</span>
      </button>
      <Icon name="chevron" size="14" class="step-arrow" />
      <button class="step" @click="$emit('navigate', 'products')">
        <span class="step-num">2</span>
        <span class="step-text">生成直播话术</span>
      </button>
      <Icon name="chevron" size="14" class="step-arrow" />
      <button class="step" @click="$emit('navigate', 'comments')">
        <span class="step-num">3</span>
        <span class="step-text">评论回复 / 复盘</span>
      </button>
    </div>

    <!-- 开播准备横幅：蓝色浅底 alert 样式（去渐变） -->
    <div class="alert alert-info prep-banner">
      <span class="prep-text">开播准备：在「商品资料」选中商品后查看资料完整度，缺什么补什么，开播更从容。</span>
      <button class="primary-btn" @click="$emit('navigate', 'products')">去完善商品资料</button>
    </div>

    <h3 class="section-title">运营概览</h3>
    <div class="stats-grid">
      <div v-for="s in STATS" :key="s.key" class="stat-card">
        <div class="stat-icon"><Icon :name="s.icon" size="18" /></div>
        <div class="stat-value">{{ stats[s.key] }}</div>
        <div class="stat-label">{{ s.label }}</div>
        <div class="stat-desc">{{ statDesc(s) }}</div>
      </div>
    </div>

    <h3 class="section-title">直播流程</h3>
    <!-- 单一连续流程带：阶段顺序与全部既有任务跳转保持不变 -->
    <div class="flow-band" aria-label="直播流程">
      <div v-for="(f, stageIndex) in FLOWS" :key="f.title" class="flow-stage">
        <div class="flow-stage-head">
          <span class="flow-stage-index">{{ stageIndex + 1 }}</span>
          <Icon :name="f.icon" size="16" class="head-icon" />
          <span class="flow-stage-title">{{ f.title }}</span>
        </div>
        <div class="flow-task-list">
          <button
            v-for="(a, taskIndex) in f.actions"
            :key="a.label"
            type="button"
            class="flow-task"
            @click="$emit('navigate', a.to)"
          >
            <span class="flow-task-index">{{ taskIndex + 1 }}</span>
            <span class="flow-task-label">{{ a.label }}</span>
            <Icon name="chevron" size="12" class="flow-task-chevron" />
          </button>
        </div>
        <span v-if="stageIndex < FLOWS.length - 1" class="flow-connector" aria-hidden="true">
          <Icon name="chevron" size="15" />
        </span>
      </div>
    </div>
  </section>
</template>

<script setup>
// 阶段 5.2：运营工作台（以旧页面已有能力为准，不新增业务功能）：
// GET /live-ops/dashboard 优先，失败时回退 GET /dashboard/stats（与旧页面一致）。
// 两个接口都失败时保持默认 0（与旧页面行为一致）。
// V6 阶段 3：欢迎区 → 三步任务引导；prep-banner 改 alert-info；统计卡统一
// （图标/标题/数字/说明 + 零值引导）；直播流程三卡任务清单化，跳转不变。
import { ref, onMounted } from "vue";
import { apiGet } from "../api/client";
import Icon from "../components/Icon.vue";

defineEmits(["navigate"]);

const stats = ref({
  product_count: 0,
  live_product_count: 0,
  live_script_count: 0,
  comment_reply_count: 0,
  live_review_count: 0,
  knowledge_document_count: 0,
});

const STATS = [
  { icon: "box", label: "商品资料", key: "product_count", unit: "个商品", zero: "暂无商品，去新增" },
  { icon: "radio", label: "直播中商品", key: "live_product_count", unit: "个直播中", zero: "当前无直播中商品" },
  { icon: "sparkles", label: "已生成话术", key: "live_script_count", unit: "条话术", zero: "选择商品后可生成" },
  { icon: "chat", label: "评论回复", key: "comment_reply_count", unit: "条回复", zero: "可在评论助手生成" },
  { icon: "chart", label: "直播复盘", key: "live_review_count", unit: "份复盘", zero: "选择商品后可生成" },
  { icon: "file", label: "商品资料文档", key: "knowledge_document_count", unit: "个文档", zero: "暂无文档，去上传" },
];

const FLOWS = [
  {
    title: "开播前",
    icon: "clock",
    actions: [
      { label: "完善商品资料", to: "products" },
      { label: "上传素材资料", to: "materials" },
      { label: "生成直播话术", to: "products" },
    ],
  },
  {
    title: "直播中",
    icon: "play",
    actions: [
      { label: "输入观众评论", to: "comments" },
      { label: "生成主播口吻回复", to: "comments" },
    ],
  },
  {
    title: "下播后",
    icon: "chart",
    actions: [
      { label: "生成直播复盘", to: "products" },
      { label: "查看优化建议", to: "products" },
    ],
  },
];

function statDesc(s) {
  const v = stats.value[s.key];
  return v ? `${v} ${s.unit}` : s.zero;
}

async function loadStats() {
  try {
    const s = await apiGet("/live-ops/dashboard");
    stats.value = s;
  } catch (e) {
    try {
      const s = await apiGet("/dashboard/stats");
      stats.value = {
        product_count: s.products,
        live_product_count: s.live_products,
        live_script_count: s.live_scripts,
        comment_reply_count: s.comment_replies,
        live_review_count: s.live_reviews,
        knowledge_document_count: s.knowledge_documents,
      };
    } catch (e2) {
      // 两个接口都失败时保持默认 0（与旧页面一致）
    }
  }
}

onMounted(loadStats);
</script>

<style scoped>
.steps-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.step {
  min-height: 32px;
  padding: 6px 12px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-pill);
  color: var(--gray-700);
}
.step:hover:not(:disabled) {
  border-color: var(--primary-border);
  color: var(--primary);
}
.step-num {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.step-arrow {
  color: var(--gray-400);
  flex-shrink: 0;
}
.prep-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 20px;
  padding: 12px 16px;
}
.prep-text {
  font-size: 13px;
  min-width: 0;
}
.prep-banner .primary-btn {
  flex-shrink: 0;
}
.section-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--gray-900);
  margin: 20px 0 14px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 16px;
}
.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  text-align: center;
}
.stat-icon {
  color: var(--primary);
  margin-bottom: 2px;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--gray-900);
}
.stat-label {
  color: var(--gray-500);
  font-size: 13px;
}
.stat-desc {
  color: var(--gray-400);
  font-size: 13px;
}
/* 三阶段连续流程带：一个统一表面，明确三等分，消除 auto-fill 的空白第四列。 */
.flow-band {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}
.flow-stage {
  position: relative;
  min-width: 0;
  padding: 20px 24px;
}
.flow-stage + .flow-stage {
  border-left: 1px solid var(--panel-border);
}
.flow-stage-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.flow-stage-index {
  width: 20px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--primary-soft);
  color: var(--primary);
  font-size: 12px;
  font-weight: 700;
}
.flow-stage-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--gray-900);
}
.flow-task-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.flow-task {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 36px;
  padding: 7px 8px;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  color: var(--gray-700);
  justify-content: flex-start;
  text-align: left;
}
.flow-task:hover:not(:disabled) {
  background: var(--gray-50);
  color: var(--primary);
}
.flow-task-index {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--gray-50);
  color: var(--gray-500);
  font-size: 12px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.flow-task-label {
  flex: 1;
  min-width: 0;
}
.flow-task-chevron {
  color: var(--gray-400);
  flex-shrink: 0;
}
/* 阶段连接：轻量箭头浮于内部边界，不引入状态或完成语义。 */
.flow-connector {
  position: absolute;
  top: 27px;
  right: -8px;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  color: var(--gray-400);
  background: var(--panel-bg);
}
@media (max-width: 768px) {
  .flow-band {
    grid-template-columns: 1fr;
  }
  .flow-stage {
    padding: 16px;
  }
  .flow-stage + .flow-stage {
    border-top: 1px solid var(--panel-border);
    border-left: none;
  }
  .flow-connector {
    top: -8px;
    right: auto;
    left: 18px;
    transform: rotate(90deg);
  }
}
@media (max-width: 390px) {
  .flow-stage {
    padding: 14px;
  }
  .flow-task {
    align-items: flex-start;
  }
  .flow-task-chevron {
    margin-top: 4px;
  }
}
</style>
