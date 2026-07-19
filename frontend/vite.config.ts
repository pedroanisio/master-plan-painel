import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

declare const process: {
  env: Record<string, string | undefined>;
};

// The dev server proxies /api to the FastAPI backend so the SPA can call the
// API on the same origin (no CORS needed during development).
const apiProxyTarget = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [svelte()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
});
