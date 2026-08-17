<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">MVP</div>
      <h1>AI 直播运营助手 <span class="title-highlight">MVP</span></h1>
      <p class="login-sub">商品资料 · 直播话术 · 评论助手 · 直播复盘<br />请输入账号和密码以进入系统</p>
      <label for="login-username">用户名</label>
      <input
        id="login-username"
        v-model="username"
        type="text"
        placeholder="用户名"
        autocomplete="username"
        :disabled="submitting"
        @keydown.enter="submit"
      />
      <label for="login-password">访问密码</label>
      <input
        id="login-password"
        v-model="password"
        type="password"
        placeholder="访问密码"
        autocomplete="off"
        :disabled="submitting"
        @keydown.enter="submit"
      />
      <div v-if="error" class="alert alert-danger login-error">{{ error }}</div>
      <button class="primary-btn login-submit" :disabled="submitting" @click="submit">
        {{ submitting ? "登录中..." : "登 录" }}
      </button>
    </div>
  </div>
</template>

<script setup>
// 阶段 5.6：登录页（与旧页面登录流程一致）：
// POST /auth/login {username, password} → 成功后 loadSession() 恢复会话；
// 空密码提示、失败提示、登录中禁用、Enter 提交。
import { ref } from "vue";
import { ApiError, SessionExpiredError } from "../api/client";
import { login, loadSession } from "../state/session";

const username = ref("");
const password = ref("");
const submitting = ref(false);
const error = ref("");

async function submit() {
  if (submitting.value) return;
  const name = username.value.trim() || "admin";
  if (!password.value) {
    error.value = "请输入访问密码";
    return;
  }

  submitting.value = true;
  error.value = "";
  try {
    await login(password.value, name);
    await loadSession();
  } catch (e) {
    if (e instanceof SessionExpiredError) {
      error.value = e.message;
    } else if (e instanceof ApiError) {
      error.value = e.detail || "登录失败";
    } else {
      error.value = "网络错误，请检查服务是否运行";
    }
    password.value = "";
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.login-card {
  width: min(400px, 100%);
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  border-radius: var(--radius);
  padding: 32px 28px;
  box-shadow: var(--shadow-sm);
}
.login-brand {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #2563eb;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  padding: 2px 10px;
  margin-bottom: 14px;
}
h1 {
  margin: 0 0 8px;
  font-size: 20px;
  color: var(--gray-900);
}
.title-highlight {
  color: var(--primary);
}
.login-sub {
  margin: 0 0 20px;
  color: var(--gray-500);
  font-size: 13px;
  line-height: 1.7;
}
input {
  width: 100%;
  font-size: 13px;
  margin-bottom: 10px;
}
.login-error {
  margin-bottom: 10px;
}
.login-submit {
  width: 100%;
}
</style>
