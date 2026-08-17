<template>
  <section class="user-view">
    <div class="user-grid">
      <!-- Left: Create user -->
      <div class="card">
        <div class="card-head">
          <h3>新增用户</h3>
        </div>
        <input v-model="newUsername" placeholder="用户名（至少 3 个字符）" />
        <input v-model="newPassword" type="password" placeholder="密码（至少 8 个字符）" />
        <select v-model="newRole">
          <option value="user">普通用户 (user)</option>
          <option value="admin">管理员 (admin)</option>
        </select>
        <button class="primary-btn" :disabled="creating" @click="createUser">
          {{ creating ? "创建中..." : "创建用户" }}
        </button>
        <div v-if="createMsg" class="create-msg" :style="{ color: createMsgColor }">{{ createMsg }}</div>
      </div>

      <!-- Right: User list -->
      <div class="card">
        <div class="card-head">
          <h3>用户列表</h3>
          <span class="count-badge">{{ users.length }}</span>
        </div>
        <div class="user-list">
          <div v-if="loading" class="hint">加载中…</div>
          <div v-else-if="listError" class="hint hint-error">用户列表加载失败。</div>
          <div v-else-if="!users.length" class="hint">暂无用户</div>
          <div v-for="u in users" :key="u.id" class="user-item">
            <div class="user-info">
              <b>{{ u.username }}</b>
              <span class="tag">{{ u.role }}</span>
              <span class="status-tag" :style="u.is_active ? activeStyle : inactiveStyle">
                {{ u.is_active ? "已启用" : "已禁用" }}
              </span>
              <div class="muted">创建：{{ createdText(u) }}</div>
            </div>
            <button class="danger-btn" :disabled="togglingId === u.id" @click="toggleStatus(u)">
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
import { ref, onMounted } from "vue";
import { apiGet, apiPost, apiPatch, ApiError, SessionExpiredError } from "../api/client";

const activeStyle = "background:#ecfdf5;color:#065f46";
const inactiveStyle = "background:#fef2f2;color:#991b1b";

const newUsername = ref("");
const newPassword = ref("");
const newRole = ref("user");
const creating = ref(false);
const createMsg = ref("");
const createMsgColor = ref("#27ae60");

const users = ref([]);
const loading = ref(false);
const listError = ref(false);
const togglingId = ref(null);

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
    createMsgColor.value = "#e74c3c";
    return;
  }
  if (password.length < 8) {
    createMsg.value = "密码至少 8 个字符";
    createMsgColor.value = "#e74c3c";
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
    createMsgColor.value = "#27ae60";
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
    createMsgColor.value = "#e74c3c";
  } finally {
    creating.value = false;
  }
}

async function toggleStatus(u) {
  const action = u.is_active ? "禁用" : "启用";
  if (!confirm(`确定要${action}该用户吗？`)) return;
  togglingId.value = u.id;
  try {
    await apiPatch(`/auth/users/${u.id}/status`, { is_active: !u.is_active });
    await loadUsers();
  } catch (e) {
    if (e instanceof SessionExpiredError) {
      alert(e.message);
    } else if (e instanceof ApiError) {
      alert(e.detail || "操作失败");
    } else {
      alert("网络错误");
    }
  } finally {
    togglingId.value = null;
  }
}

onMounted(loadUsers);
</script>

<style scoped>
.user-view {
  max-width: var(--content-max);
  margin: 0 auto;
  padding: 24px 20px;
}
.user-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  align-items: start;
}
@media (max-width: 900px) {
  .user-grid {
    grid-template-columns: 1fr;
  }
}
input,
select {
  margin-bottom: 8px;
}
.create-msg {
  margin-top: 8px;
  font-size: 13px;
}
.user-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  padding: 10px 4px;
  border-bottom: 1px solid #f3f4f6;
}
.user-item:last-child {
  border-bottom: none;
}
.user-info {
  min-width: 0;
}
.user-info b {
  font-size: 13px;
}
.user-item .tag,
.user-item .status-tag {
  margin-left: 6px;
}
.list-footer {
  margin-top: 10px;
}
</style>
