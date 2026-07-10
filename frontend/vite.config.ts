import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/intercept': 'http://localhost:8000',
      '/tools': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/bootstrap': 'http://localhost:8000',
      '/resolve': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/timeline': 'http://localhost:8000',
    },
  },
})
