/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Replicate's API does not support CORS from browser origins, so we
      // proxy through the dev server (and nginx in production). The proxy is
      // transparent — it forwards the user's Authorization header and never
      // persists request bodies or headers.
      "/replicate-api": {
        target: "https://api.replicate.com",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/replicate-api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.ts",
    globals: true,
  },
});
