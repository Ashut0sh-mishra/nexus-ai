import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // VITE_PROXY_TARGET is used by the dev server only (server-side fetch),
  // so inside Docker it must be the compose service URL (e.g. http://backend:8000).
  // VITE_BACKEND_URL is what the browser uses; leave unset to use the relative
  // "/api" prefix and route through this dev proxy.
  const backend =
    env.VITE_PROXY_TARGET || env.VITE_BACKEND_URL || "http://localhost:8080";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: true,
      proxy: {
        "/api": {
          target: backend,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: false,
      target: "es2020",
    },
  };
});
