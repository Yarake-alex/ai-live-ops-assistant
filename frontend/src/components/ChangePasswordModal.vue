<template>
  <div class="modal-overlay" @click.self="close">
    <div class="modal-box cp-box">
      <div class="modal-head">
        <h3>修改密码</h3>
        <button class="close-btn" @click="close"><Icon name="x" size="14" /></button>
      </div>
      <label for="cp-old">当前密码</label>
      <input id="cp-old" v-model="oldPassword" type="password" placeholder="当前密码" :disabled="saving" />
      <label for="cp-new">新密码（至少 6 个字符）</label>
      <input id="cp-new" v-model="newPassword" type="password" placeholder="新密码（至少 6 个字符）" :disabled="saving" />
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
import Icon from "./Icon.vue";

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
.cp-box {
  width: min(400px, calc(100vw - 32px));
}
.cp-box input {
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
</style>
