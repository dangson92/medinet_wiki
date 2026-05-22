/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

// Phase 5 Wave 0 (VALIDATION.md §"Wave 0 Requirements")
// jsdom environment cho @testing-library/react render + window/document API.
// Mirror tsconfig.json path alias `@/*` → repo root (cùng cấu hình vite.config.ts).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    css: false, // skip CSS parsing cho test perf (Tailwind không cần ở unit test)
    include: ['src/**/__tests__/**/*.{ts,tsx,spec.ts,spec.tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      exclude: ['**/__tests__/**', '**/*.d.ts', 'vite.config.ts', 'vitest.config.ts'],
    },
  },
});
