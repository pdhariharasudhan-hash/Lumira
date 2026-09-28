import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5000,
    strictPort: true,
    proxy: {
      "/brain": "http://127.0.0.1:8000",
      "/command": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
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
  },
})
