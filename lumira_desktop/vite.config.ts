import { createRequire } from "node:module";
import type { Plugin } from "vite";
import { configDefaults, defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const require = createRequire(import.meta.url);
const { createApiProxyHandler } = require("./electron-api-proxy.cjs") as {
  createApiProxyHandler: (port: number) => (req: import("node:http").IncomingMessage, res: import("node:http").ServerResponse) => boolean;
};

const apiPort = Number(process.env.LUMIRA_API_PORT || 8000);

function lumiraApiProxy(): Plugin {
  const proxyApiRequest = createApiProxyHandler(apiPort);
  const install = (server: { middlewares: { use: (handler: (req: import("node:http").IncomingMessage, res: import("node:http").ServerResponse, next: (error?: Error) => void) => void) => void } }) => {
    server.middlewares.use((req, res, next) => {
      if (!proxyApiRequest(req, res)) next();
    });
  };

  return {
    name: "lumira-api-proxy",
    configureServer: install,
    configurePreviewServer: install,
  };
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), lumiraApiProxy()],
  server: {
    // Keep the local personal-AI workbench off the LAN by default.
    host: "127.0.0.1",
    port: 5000,
    strictPort: true,
  },
  preview: {
    host: "127.0.0.1",
  },
  test: {
    environment: "jsdom",
    clearMocks: true,
    restoreMocks: true,
    // The vmThreads pool stalled without reporting test files on this Windows setup.
    // The threads pool is verified here and remains bounded to one worker.
    pool: "threads",
    maxWorkers: 1,
    fileParallelism: false,
    // This CommonJS file uses Node built-in tests and runs separately.
    exclude: [...configDefaults.exclude, "**/*.test.cjs"],
  },
});
