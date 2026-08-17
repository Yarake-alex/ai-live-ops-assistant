// 全局轻提示与确认框（替代原生 alert/confirm，不引入任何依赖）。
// 用法：
//   import { toast, confirmDialog } from "../state/feedback";
//   toast("资料已删除", "success");
//   toast("操作失败，请稍后重试。", "error");
//   const ok = await confirmDialog("确定要删除吗？", { danger: true });
import { reactive } from "vue";

export const toasts = reactive([]);
let toastSeq = 0;

const TOAST_DURATIONS = { info: 2600, success: 2600, error: 4000 };

export function toast(message, type = "info", duration) {
  const id = ++toastSeq;
  toasts.push({ id, message, type });
  const ms = duration || TOAST_DURATIONS[type] || 2600;
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id);
    if (i !== -1) toasts.splice(i, 1);
  }, ms);
}

export const confirmState = reactive({
  visible: false,
  message: "",
  danger: false,
  _resolve: null,
});

export function confirmDialog(message, { danger = false } = {}) {
  confirmState.message = message;
  confirmState.danger = danger;
  confirmState.visible = true;
  return new Promise((resolve) => {
    confirmState._resolve = resolve;
  });
}

export function resolveConfirm(ok) {
  confirmState.visible = false;
  const r = confirmState._resolve;
  confirmState._resolve = null;
  if (r) r(ok);
}
