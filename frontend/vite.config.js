import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// build: GitHub Pages lo sirve bajo /crypto-bot/ (RF-8); dev: raíz local.
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/crypto-bot/' : '/',
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
  },
}))
