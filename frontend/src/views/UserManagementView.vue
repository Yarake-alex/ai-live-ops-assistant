<template>
  <section class="user-view container">
    <div class="view-head">
      <div>
        <h2 class="view-title">用户管理</h2>
        <p class="view-desc">管理可登录系统的账号与角色（仅管理员可见）</p>
      </div>
      <div class="view-actions">
        <button class="primary-btn" @click="focusCreate">
          <Icon name="plus" size="14" /> 新增用户
        </button>
      </div>
    </div>

    <div class="user-grid">
      <!-- Left: Create user (side, 40%) -->
      <div class="card">
        <div class="card-head">
          <h3><Icon name="users" size="15" class="head-icon" /> 新增用户</h3>
        </div>
        <label for="um-username">用户名（至少 3 个字符）</label>
        <input id="um-username" ref="usernameInput" v-model="newUsername" placeholder="用户名（至少 3 个字符）" />
        <label for="um-password">密码（至少 8 个字符）</label>
        <input id="um-password" v-model="newPassword" type="password" placeholder="密码（至少 8 个字符）" />
        <label for="um-role">角色</label>
        <select id="um-role" v-model="newRole">
          <option value="user">普通用户 (user)</option>
          <option value="admin">管理员 (admin)</option>
        </select>
        <button class="primary-btn" :disabled="creating" @click="createUser">
          {{ creating ? "创建中..." : "创建用户" }}
        </button>
        <div v-if="createMsg" class="alert create-msg" :class="createOk ? 'alert-success' : 'alert-danger'">
          {{ createMsg }}
        </div>
      </div>

      <!-- Right: User list (main, 60%) -->
      <div class="card">
        <div class="card-head">
          <h3>用户列表</h3>
          <span class="count-badge">{{ users.length }} 个用户</span>
        </div>
        <div class="user-list">
          <div v-if="loading" class="hint">加载中…</div>
          <div v-else-if="listError" class="hint hint-error">用户列表加载失败。</div>
          <div v-else-if="!users.length" class="empty">
            <span class="empty-icon"><Icon name="users" size="32" /></span>
            <span>暂无用户</span>
          </div>
          <div v-for="u in users" :key="u.id" class="row-item">
            <div class="user-info">
              <b>{{ u.username }}</b>
              <span class="tag" :class="u.role === 'admin' ? 'tag-primary' : ''">{{ u.role }}</span>
              <span class="tag" :class="u.is_active ? 'tag-success' : 'tag-danger'">
                {{ u.is_active ? "已启用" : "已禁用" }}
              </span>
              <div class="muted">创建：{{ createdText(u) }}</div>
            </div>
            <button
              :class="u.is_active ? 'danger-btn' : 'light-btn'"
              :disabled="togglingId === u.id"
              @click="toggleStatus(u)"
            >
              {{ u.is_active ? "禁用" : "启用" }}
            </button>
          </div>
        </div>
        <div class="list-footer">
          <button class="light-btn" :disabled="loading" @click="loadUsers">刷新列表</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
// 阶段 5.4：用户管理（以旧页面已有能力为准，不新增权限模型）：
// GET /auth/users 列表、POST /auth/users 创建、PATCH /auth/users/{id}/status 启用/禁用。
// 修改密码属于页头登录态功能，不在本页迁移范围。
// V6 阶段 6：标题区「新增用户」聚焦表单；稳定双栏（列表主宽 60%）；
// 角色/状态用统一 tag，禁用用危险操作样式。
import { ref, onMounted } from "vue";
import { apiGet, apiPost, apiPatch, ApiError, SessionExpiredError } from "../api/client";
import { toast, confirmDialog } from "../state/feedback";
import Icon from "../components/Icon.vue";

const usernameInput = ref(null);
const newUsername = ref("");
const newPassword = ref("");
const newRole = ref("user");
const creating = ref(false);
const createMsg = ref("");
const createOk = ref(false);

const users = ref([]);
const loading = ref(false);
const listError = ref(false);
const togglingId = ref(null);

function focusCreate() {
  usernameInput.value?.scrollIntoView({ block: "center", behavior: "smooth" });
  usernameInput.value?.focus();
}

function createdText(u) {
  return u.created_at ? new Date(u.created_at).toLocaleDateString() : "";
}

async function loadUsers() {
  loading.value = true;
  listError.value = false;
  try {
    users.value = await apiGet("/auth/users");
  } catch (e) {
    listError.value = true;
    users.value = [];
  } finally {
    loading.value = false;
  }
}

async function createUser() {
  const username = newUsername.value.trim();
  const password = newPassword.value;
  if (username.length < 3) {
    createMsg.value = "用户名至少 3 个字符";
    createOk.value = false;
    return;
  }
  if (password.length < 8) {
    createMsg.value = "密码至少 8 个字符";
    createOk.value = false;
    return;
  }

  creating.value = true;
  createMsg.value = "";
  try {
    const data = await apiPost("/auth/users", {
      username,
      password,
      role: newRole.value,
    });
    createMsg.value = `用户 ${data.username} 创建成功`;
    createOk.value = true;
    newUsername.value = "";
    newPassword.value = "";
    newRole.value = "user";
    await loadUsers();
  } catch (e) {
    if (e instanceof SessionExpiredError) {
      createMsg.value = e.message;
    } else if (e instanceof ApiError) {
      createMsg.value = e.detail || "创建失败";
    } else {
      createMsg.value = "网络错误";
    }
    createOk.value = false;
  } finally {
    creating.value = false;
  }
}

async function toggleStatus(u) {
  const action = u.is_active ? "禁用" : "启用";
  if (!(await confirmDialog(`确定要${action}该用户吗？`, { danger: u.is_active }))) return;
  togglingId.value = u.id;
  try {
    await apiPatch(`/auth/users/${u.id}/status`, { is_active: !u.is_active });
    await loadUsers();
  } catch (e) {
    if (e instanceof SessionExpiredError) {
      toast(e.message, "error");
    } else if (e instanceof ApiError) {
      toast(e.detail || "操作失败", "error");
    } else {
      toast("网络错误", "error");
    }
  } finally {
    togglingId.value = null;
  }
}

onMounted(loadUsers);
</script>

<style scoped>
/* 稳定双栏：表单侧 40%，用户列表主宽 60%；窄屏自动堆叠 */
.user-grid {
  display: grid;
  grid-template-columns: minmax(280px, 2fr) minmax(0, 3fr);
  gap: 16px;
  align-items: start;
}
@media (max-width: 900px) {
  .user-grid {
    grid-template-columns: 1fr;
  }
}
.user-grid input,
.user-grid select {
  margin-bottom: 8px;
}
.create-msg {
  margin-top: 8px;
}
.user-info {
  min-width: 0;
}
.user-info b {
  font-size: 13px;
}
.user-info .tag {
  margin-left: 6px;
}
.list-footer {
  margin-top: 10px;
}
</style>
