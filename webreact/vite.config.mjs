import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendPort = process.env.VITE_BACKEND_PORT || "8000";

export default defineConfig({
  server: {
    port: 5174,
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
  plugins: [react()],
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
