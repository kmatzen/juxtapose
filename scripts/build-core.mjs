import { build } from 'vite';

// script.js runs as CommonJS under jsdom, so the core needs a CJS artifact next to the browser bundle.
await build({
  configFile: false,
  logLevel: 'warn',
  build: {
    lib: { entry: 'frontend/src/study-state.ts', formats: ['cjs'], fileName: () => 'study-state.cjs' },
    outDir: 'frontend/.cjs',
    emptyOutDir: true,
    minify: false,
  },
});
