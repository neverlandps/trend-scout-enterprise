import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules')) {
            if (id.includes('recharts') || id.includes('d3-')) {
              return 'recharts'
            }
            if (id.includes('@fluentui')) {
              return 'fluentui'
            }
            if (id.includes('react-router-dom') || id.includes('react-router')) {
              return 'router'
            }
            return 'vendor'
          }
        },
      },
    },
  },
})
