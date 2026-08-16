<template>
  <div class="cp-overlay" @click.self="close">
    <div class="cp-box">
      <div class="cp-head">
        <h3>修改密码</h3>
        <button class="close-btn" @click="close">✕</button>
      </div>
      <input v-model="oldPassword" type="password" placeholder="当前密码" :disabled="saving" />
      <input v-model="newPassword" type="password" placeholder="新密码（至少 6 个字符）" :disabled="saving" />
      <div v-if="msg" class="cp-msg" :style="{ color: msgColor }">{{ msg }}</div>
      <div class="cp-actions">
        <button class="primary-btn" :disabled="saving" @click="submit">
          {{ saving ? "提交中..." : "确认修改" }}
        </button>
        <button class="light-btn" :disabled="saving" @click="close">取消</button>
      </div>
    </div>
  </div>
</template>

<script setup>
// 阶段 5.5：修改密码（与旧页面一致）：
// POST /auth/change-password {old_password, new_password}；
// 成功提示后退出登录（旧页面行为：修改成功后需重新登录）。
import { ref } from "vue";
import { apiPost, ApiError, SessionExpiredError } from "../api/client";
import { session, logout } from "../state/session";

const emit = defineEmits(["close"]);

const oldPassword = ref("");
const newPassword = ref("");
const saving = ref(false);
const msg = ref("");
const msgColor = ref("#e74c3c");

function close() {
  if (saving.value) return;
  oldPassword.value = "";
  newPassword.value = "";
  msg.value = "";
  emit("close");
}

async function submit() {
  if (saving.value) return;
  if (!oldPassword.value) {
    msg.value = "请输入当前密码";
    msgColor.value = "#e74c3c";
    return;
  }
  if (!newPassword.value || newPassword.value.length < 6) {
    msg.value = "新密码至少 6 个字符";
    msgColor.value = "#e74c3c";
    return;
  }

  saving.value = true;
  msg.value = "";
  try {
    await apiPost("/auth/change-password", {
      old_password: oldPassword.value,
      new_password: newPassword.value,
    });
    msg.value = "密码修改成功，请使用新密码重新登录";
    msgColor.value = "#27ae60";
    // 旧页面行为：修改成功后自动退出登录
    setTimeout(async () => {
      await logout();
      close();
    }, 1500);
  } catch (e) {
    if (e instanceof SessionExpiredError) {
      msg.value = e.message;
    } else if (e instanceof ApiError) {
      msg.value = e.detail || "修改失败";
    } else {
      msg.value = "网络错误";
    }
    msgColor.value = "#e74c3c";
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.cp-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.cp-box {
  width: min(400px, calc(100vw - 32px));
  background: #fff;
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
}
.cp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.cp-head h3 {
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
input {
  width: 100%;
  font-size: 13px;
  margin-bottom: 8px;
}
.cp-msg {
  font-size: 13px;
  margin: 4px 0 8px;
}
.cp-actions {
  display: flex;
  gap: 8px;
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
