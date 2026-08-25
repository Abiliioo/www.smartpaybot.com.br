import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  base: '/static/dist/',
  plugins: [react()],
  build: {
    outDir: '../app/static/dist',
    emptyOutDir: true,
    manifest: true,
    assetsDir: 'assets',
  },
})
