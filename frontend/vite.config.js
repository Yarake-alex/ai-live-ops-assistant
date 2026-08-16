import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// V5 最小骨架：仅组件化基础设施，不迁移业务页面。
// 后续逐页迁移时再补充后端代理等配置（当前不改后端，不配代理）。
export default defineConfig({
  plugins: [vue()],
});
