/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    proxy: {
      // ws:true so the live terminal WebSockets (/api/terminals/*/ws) proxy too.
      "/api": { target: "http://127.0.0.1:8787", ws: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
