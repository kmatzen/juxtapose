import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';

const frontendRoot = fileURLToPath(new URL('.', import.meta.url));
const legacyStatic = fileURLToPath(new URL('../src/survey/static', import.meta.url));
const outDir = fileURLToPath(new URL('../src/survey/static_dist', import.meta.url));

export default defineConfig({
  root: frontendRoot,
  // Legacy classic scripts pass through untouched: the pipeline is proven before any rewrite.
  publicDir: legacyStatic,
  build: {
    outDir,
    emptyOutDir: true,
    manifest: true,
    minify: false,
    target: 'esnext',
    rollupOptions: {
      input: { main: fileURLToPath(new URL('./src/main.ts', import.meta.url)) },
    },
  },
});
