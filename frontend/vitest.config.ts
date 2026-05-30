import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      'next/link': path.resolve(__dirname, 'src/compat/next-link.tsx'),
      'next/navigation': path.resolve(__dirname, 'src/compat/next-navigation.ts'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
  },
});
