import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'

export default defineConfig({
  build: {
    emptyOutDir: true,
    lib: {
      entry: fileURLToPath(new URL('./src/index.ts', import.meta.url)),
      fileName: 'index',
      formats: ['es'],
    },
    minify: false,
    outDir: fileURLToPath(new URL('./dist', import.meta.url)),
    sourcemap: true,
  },
})
