/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: './',
  build: { outDir: 'dist', emptyOutDir: true, sourcemap: false, cssCodeSplit: false },
  server: { strictPort: true },
  // The tests that mount the whole Desktop take 1 to 3 seconds each alone and pass the default 5 second limit when
  // every test file runs at once on a busy PC. The limit only decides when a test counts as hung.
  test: { testTimeout: 20000 },
})
