import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
// El backend sirve el build en http://127.0.0.1:8000/ (sin Render ni GitHub Pages).
export default defineConfig(() => ({
  base: '/',
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
  },
}))
