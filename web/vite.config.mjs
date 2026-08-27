import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/static": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("@phosphor-icons")) return "icon-vendor";
          if (id.includes("vue") || id.includes("pinia")) return "vue-vendor";
          if (id.includes("qrcode")) return "qr-tools";
          if (id.includes("marked")) return "markdown-tools";
          if (id.includes("axios")) return "network-vendor";
          return "vendor";
        },
      },
    },
  },
});
