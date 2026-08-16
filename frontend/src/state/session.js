// 简单会话状态：使用 Vue 自带 reactive，不引入 Pinia 或其他状态库。
// 骨架阶段仅提供登录态恢复与基本读写；业务页迁移后再接入登录页跳转与展示。

import { reactive } from "vue";
import { apiGet, apiPost } from "../api/client";

export const session = reactive({
  user: null, // 当前登录用户（后端 UserOut：username / role / is_active）
  loaded: false, // 是否已尝试恢复会话
  error: "",
});

// 页面加载时尝试恢复登录态（Cookie 会话有效则 /auth/me 返回当前用户）
export async function loadSession() {
  try {
    const me = await apiGet("/auth/me");
    session.user = me;
    session.error = "";
  } catch (e) {
    session.user = null;
  } finally {
    session.loaded = true;
  }
}

// 访问密码登录（与后端 /auth/login 约定一致：{ password }）
export async function login(password) {
  const data = await apiPost("/auth/login", { password });
  session.user = data;
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
