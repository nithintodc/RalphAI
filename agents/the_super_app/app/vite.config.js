import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const SUPER_APP_PORT = 5180
const SUPER_APP_BASE = '/internal-apps/the-super-app/'

export default defineConfig({
  base: SUPER_APP_BASE,
  plugins: [react(), tailwindcss()],
  server: {
    port: SUPER_APP_PORT,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/export': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/export-doc': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: SUPER_APP_PORT,
    strictPort: true,
  },
})
