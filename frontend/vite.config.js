import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Proxy target is server-side only (Node). Do NOT use VITE_ prefix or it leaks to the browser bundle.
  const backend = env.BACKEND_PROXY_URL || env.VITE_BACKEND_URL || "http://localhost:8080";
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
