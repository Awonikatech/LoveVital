/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

const API = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": { target: API, changeOrigin: true },
      "/static": { target: API, changeOrigin: true },
      "/media": { target: API, changeOrigin: true },
    },
  },
  preview: { port: 4173, proxy: { "/api": API, "/static": API, "/media": API } },
  build: {
    sourcemap: false,
    rollupOptions: { output: { manualChunks: { react: ["react", "react-dom", "react-router-dom"], charts: ["recharts"] } } },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});
