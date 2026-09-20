import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const backendPort = process.env.VITE_BACKEND_PORT || "8000";

export default defineConfig({
  server: {
    port: 5174,
    // 端口必须固定：导航栏「学习空间」是跨源 iframe，openmaic-app 只放行
    // 5174 两个 Origin 的 frame-ancestors。自动漂移（如 5175）不会报端口错，
    // 只会让 iframe 被浏览器按 CSP 拒掉（控制台报 frame-ancestors 违规），
    // 表现为「学习空间」打不开。
    strictPort: true,
    // 编辑器与 AI 工具常以"写临时文件再原子改名"的方式保存，临时目录形如
    // `.Foo.jsx.<pid>.<uuid>.tmpdir/`。chokidar 默认会 watch 这些瞬时目录，
    // 它们在改名瞬间就消失，Windows 上表现为 EBUSY 直接打崩 dev server。
    // 只影响 watch，不影响构建产物。
    watch: {
      ignored: ["**/.*.tmpdir/**", "**/*.tmpdir/**", "**/*.tmp"],
    },
    proxy: {
      "/api": { target: `http://127.0.0.1:${backendPort}`, changeOrigin: true },
      "/static": { target: `http://127.0.0.1:${backendPort}`, changeOrigin: true },
    },
  },
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        onlyExplicitManualChunks: true,
        manualChunks(id) {
          const moduleId = id.replaceAll("\\", "/");
          if (!moduleId.includes("node_modules")) return undefined;
          if (moduleId.endsWith(".css")) return undefined;
          if (moduleId.includes("@designcodeio/threeui") || moduleId.includes("@react-three") || moduleId.includes("node_modules/three/") || moduleId.includes("node_modules/three-stdlib/") || moduleId.includes("node_modules/postprocessing/")) return "route-3d-vendor";
          return undefined;
        },
      },
    },
  },
});
