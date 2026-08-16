// 简单会话状态：使用 Vue 自带 reactive，不引入 Pinia 或其他状态库。
// 提供登录态恢复、登录、退出；401 时自动清空会话（回到登录页，与旧页面一致）。

import { reactive } from "vue";
import { apiGet, apiPost, onSessionExpired } from "../api/client";

export const session = reactive({
  user: null, // 当前登录用户（后端 UserOut：username / role / is_active）
  loaded: false, // 是否已尝试恢复会话
  error: "",
});

// 任意接口返回 401 时，自动清空会话 → 登录页（旧页面 showLogin 行为）
onSessionExpired(() => {
  session.user = null;
  session.loaded = true;
});

// 页面加载时尝试恢复登录态（/auth/me：已登录返回用户信息，未登录返回 { logged_in: false }）
export async function loadSession() {
  try {
    const me = await apiGet("/auth/me");
    session.user = me && me.logged_in !== false ? me : null;
    session.error = "";
  } catch (e) {
    session.user = null;
  } finally {
    session.loaded = true;
  }
}

// 访问密码登录（与后端 /auth/login 约定一致：{ username, password }）
export async function login(password, username) {
  const data = await apiPost("/auth/login", {
    username: username || undefined,
    password,
  });
  session.error = "";
  return data;
}

export async function logout() {
  try {
    await apiPost("/auth/logout");
  } finally {
    session.user = null;
  }
}
