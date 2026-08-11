import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Production under nginx: VITE_BASE_PATH=/uorf-explorer/
// Local Vite proxy: leave unset (defaults to /)
const base = process.env.VITE_BASE_PATH || "/";

export default defineConfig({
  plugins: [react()],
  base: base.endsWith("/") ? base : `${base}/`,
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8001",
      "/tracks": "http://127.0.0.1:8001",
      "/reference": "http://127.0.0.1:8001",
    },
  },
});
