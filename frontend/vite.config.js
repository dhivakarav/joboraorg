import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/internship": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
      "/job": {
        target: "http://localhost:8001",
        changeOrigin: true,
      },
    },
  },
});
