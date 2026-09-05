import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  server: {
    port: 5174,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/static": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("@phosphor-icons")) return "icon-vendor";
          if (id.includes("react-router") || id.includes("react-dom")) return "react-vendor";
          if (id.includes("qrcode")) return "qr-tools";
          if (id.includes("marked")) return "markdown-tools";
          if (id.includes("axios")) return "network-vendor";
          return "vendor";
        },
      },
    },
  },
});
