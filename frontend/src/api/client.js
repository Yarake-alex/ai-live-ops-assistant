// 统一 API 请求封装：fetch + JSON 解析 + 错误处理。
// 与后端约定：业务接口返回 JSON；401 视为登录失效，抛出 SessionExpiredError。
// 接口路径与返回结构保持不变，仅封装前端请求逻辑。

export class SessionExpiredError extends Error {
  constructor(message = "登录已失效，请重新登录") {
    super(message);
    this.name = "SessionExpiredError";
  }
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `请求失败（HTTP ${status}）`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function parseBody(resp) {
  const text = await resp.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function apiRequest(url, options = {}) {
  const { headers = {}, ...rest } = options;
  const isJsonBody = rest.body !== undefined && typeof rest.body === "string";
  const resp = await fetch(url, {
    credentials: "include",
    ...rest,
    headers: {
      ...(isJsonBody ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
  });

  const data = await parseBody(resp);

  if (resp.status === 401) {
    throw new SessionExpiredError();
  }
  if (!resp.ok) {
    const detail = data && typeof data === "object" && data.detail ? data.detail : undefined;
    throw new ApiError(resp.status, detail);
  }
  return data;
}

export function apiGet(url) {
  return apiRequest(url);
}

export function apiPost(url, body) {
  return apiRequest(url, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function apiPut(url, body) {
  return apiRequest(url, {
    method: "PUT",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function apiPatch(url, body) {
  return apiRequest(url, {
    method: "PATCH",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function apiDelete(url) {
  return apiRequest(url, { method: "DELETE" });
}
