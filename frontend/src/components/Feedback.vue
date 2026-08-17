<template>
  <teleport to="body">
    <!-- 轻提示：底部居中，aria-live 播报 -->
    <div class="toast-stack" aria-live="polite">
      <TransitionGroup name="toast">
        <div v-for="t in toasts" :key="t.id" class="toast" :class="'toast-' + t.type" role="status">
          <Icon :name="toastIcon(t.type)" size="14" class="toast-icon" />
          <span class="toast-text">{{ t.message }}</span>
        </div>
      </TransitionGroup>
    </div>

    <!-- 统一确认弹窗：危险操作用红色主按钮 -->
    <div v-if="confirmState.visible" class="modal-overlay" @click.self="resolveConfirm(false)">
      <div class="modal-box confirm-box">
        <div class="modal-head">
          <h3>确认操作</h3>
          <button class="close-btn" aria-label="关闭" @click="resolveConfirm(false)">
            <Icon name="x" size="14" />
          </button>
        </div>
        <div class="confirm-message">{{ confirmState.message }}</div>
        <div class="confirm-actions">
          <button class="light-btn" autofocus @click="resolveConfirm(false)">取消</button>
          <button
            :class="confirmState.danger ? 'danger-btn' : 'primary-btn'"
            @click="resolveConfirm(true)"
          >
            确定
          </button>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
// V6 质量收口：全站统一的轻提示与确认弹窗（替代原生 alert/confirm）。
// 复用全局 .modal-* 样式；无新增依赖。
import { toasts, confirmState, resolveConfirm } from "../state/feedback";
import Icon from "./Icon.vue";

function toastIcon(type) {
  if (type === "success") return "check";
  if (type === "error") return "x";
  return "help";
}
</script>

<style scoped>
.toast-stack {
  position: fixed;
  left: 50%;
  bottom: 28px;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  z-index: 200;
  pointer-events: none;
  width: max-content;
  max-width: calc(100vw - 32px);
}
.toast {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  max-width: 100%;
  padding: 9px 14px;
  border-radius: var(--radius-sm);
  background: var(--gray-900);
  color: #fff;
  font-size: 13px;
  line-height: 1.6;
  box-shadow: var(--shadow-md);
  pointer-events: auto;
}
.toast-icon {
  flex-shrink: 0;
  margin-top: 2px;
}
.toast-success .toast-icon {
  color: #34d399;
}
.toast-error .toast-icon {
  color: #f87171;
}
.toast-info .toast-icon {
  color: #93c5fd;
}
.toast-text {
  white-space: pre-line;
  word-break: break-all;
}
.toast-enter-active,
.toast-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
.confirm-box {
  width: min(440px, calc(100vw - 32px));
}
.confirm-message {
  font-size: 13px;
  color: var(--gray-700);
  line-height: 1.8;
  white-space: pre-line;
  word-break: break-all;
}
.confirm-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
