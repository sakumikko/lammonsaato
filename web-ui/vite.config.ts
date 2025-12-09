import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  // Use relative paths for assets when building for HA add-on
  base: "./",
  server: {
    host: "::",
    // Different ports for different modes so both can run simultaneously
    // dev (real HA): 8080, dev:test (mock): 8081
    port: mode === "test" ? 8081 : 8080,
    // In test mode, proxy HA API requests to mock server
    proxy: mode === "test" ? {
      // WebSocket proxy for HA protocol
      "/api/websocket": {
        target: "ws://localhost:8765",
        ws: true,
        changeOrigin: true,
      },
      // REST API proxy
      "/api": {
        target: "http://localhost:8765",
        changeOrigin: true,
      },
    } : undefined,
  },
  plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "dist",
    sourcemap: mode === "development",
  },
}));
