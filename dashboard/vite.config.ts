import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/internal-apps": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/export": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/export-doc": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
