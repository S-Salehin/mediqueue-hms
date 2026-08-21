import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_API_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
  test: {
    environment: 'jsdom',
    exclude: ['e2e/**', 'node_modules/**', 'dist/**', 'coverage/**'],
    setupFiles: './src/test/setup.js',
    css: true,
    restoreMocks: true,
    coverage: {
      include: [
        'src/api/**/*.{js,jsx}',
        'src/context/**/*.{js,jsx}',
        'src/hooks/**/*.{js,jsx}',
        'src/utils/**/*.{js,jsx}',
      ],
      exclude: ['src/**/*.test.{js,jsx}', 'src/test/**'],
      thresholds: { lines: 75, statements: 75, functions: 75, branches: 75 },
    },
  },
})
