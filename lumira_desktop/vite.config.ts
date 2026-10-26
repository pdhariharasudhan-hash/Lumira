import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Keep the local personal-AI workbench off the LAN by default.
    // Exposing the proxy can bypass the backend's loopback-only trust boundary.
    host: '127.0.0.1',
    port: 5000,
    strictPort: true,
    proxy: {
      "/brain": "http://127.0.0.1:8000",
      "/command": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/intelligence": "http://127.0.0.1:8000",
      "/images": "http://127.0.0.1:8000",
      "/modes": "http://127.0.0.1:8000",
      "/features": "http://127.0.0.1:8000",
      "/notepad": "http://127.0.0.1:8000",
      "/sessions": "http://127.0.0.1:8000",
      "/memory": "http://127.0.0.1:8000",
      "/projects": "http://127.0.0.1:8000",
      "/artifacts": "http://127.0.0.1:8000",
      "/goals": "http://127.0.0.1:8000",
      "/workflows": "http://127.0.0.1:8000",
      "/search": "http://127.0.0.1:8000",
      "/runs": "http://127.0.0.1:8000",
      "/voice": "http://127.0.0.1:8000",
      "/devices": "http://127.0.0.1:8000",
      "/openapi.json": "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: 'jsdom',
    clearMocks: true,
    restoreMocks: true,
    // The vmThreads pool stalled without reporting test files on this Windows setup.
    // The threads pool is verified here and remains bounded to one worker.
    pool: 'threads',
    maxWorkers: 1,
    fileParallelism: false,
  },
})
