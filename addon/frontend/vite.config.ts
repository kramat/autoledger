import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// base './' keeps every asset URL relative, which Ingress needs: the app is
// served under /api/hassio_ingress/<token>/.
export default defineConfig({
  base: './',
  plugins: [vue()],
  build: { chunkSizeWarningLimit: 800 }, // ECharts is most of the bundle
  server: {
    proxy: { '/api': 'http://localhost:8099' },
  },
})
