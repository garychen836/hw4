import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Forward API and image requests to the FastAPI backend on port 8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/media': 'http://localhost:8000',
    },
  },
})
