import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// V5 迁移骨架：组件化基础设施 + 逐页迁移。
// dev 代理只做转发，前端仍以原路径（/rag、/auth 等）请求，后端接口不变。
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      "/rag": "http://127.0.0.1:8000",
      "/auth": "http://127.0.0.1:8000",
      "/products": "http://127.0.0.1:8000",
    },
  },
});
