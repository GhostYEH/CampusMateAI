import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendPort = process.env.VITE_BACKEND_PORT || "8000";

export default defineConfig({
  server: {
    port: 5174,
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
