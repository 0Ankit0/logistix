import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const publicEnv = Object.fromEntries(
    Object.entries(env).filter(([key]) => key.startsWith('NEXT_PUBLIC_') || key.startsWith('VITE_'))
  );

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
        'next/link': path.resolve(__dirname, 'src/compat/next-link.tsx'),
        'next/navigation': path.resolve(__dirname, 'src/compat/next-navigation.ts'),
      },
    },
    define: {
      'process.env': publicEnv,
    },
    server: {
      port: 3000,
      host: '0.0.0.0',
      proxy: {
        '/api/v1': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
    preview: {
      port: 3000,
      host: '0.0.0.0',
    },
  };
});