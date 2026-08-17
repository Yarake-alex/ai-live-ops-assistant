// 生成任务状态（轻量模块，模式与 state/feedback.js 一致，不引入状态库）。
// 直播话术 / 直播复盘的生成请求在组件卸载后仍会在后台完成：
// 组件本地 generating ref 会随卸载丢失，因此把任务状态提升到模块级，
// 按 productId 隔离保存，切换 tab / 切回页面时据此恢复「生成中」或完成结果。
//
// 用法：
//   import { getGeneration, startGeneration, finishGeneration } from "../state/generationTasks";
//   startGeneration("liveScript", productId);
//   finishGeneration("liveScript", productId, { result: data });
//   finishGeneration("liveScript", productId, { error: true });
//   const task = getGeneration("liveScript", productId); // { pending, error, result, startedAt } | null
import { reactive } from "vue";

export const generationTasks = reactive({
  liveScript: {}, // productId -> { pending, error, result, startedAt }
  liveReview: {},
});

export function startGeneration(kind, productId) {
  generationTasks[kind][productId] = {
    pending: true,
    error: false,
    result: null,
    startedAt: Date.now(),
  };
}

export function finishGeneration(kind, productId, { result = null, error = false } = {}) {
  const prev = generationTasks[kind][productId] || {};
  generationTasks[kind][productId] = {
    pending: false,
    error,
    result,
    startedAt: prev.startedAt ?? null,
  };
}

export function getGeneration(kind, productId) {
  if (productId == null) return null;
  return generationTasks[kind][productId] || null;
}
