import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Relative assets work from GitHub Pages subpaths AND STAR Desktop's local file:// shell.
export default defineConfig({
  plugins: [react()],
  base: './',
  build: { target: 'es2022', assetsDir: 'assets', outDir: 'dist', sourcemap: false },
});
