import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'static/dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        components: path.resolve(__dirname, 'components/index.jsx'),
      },
      output: {
        entryFileNames: 'components.js',
        chunkFileNames: 'components-[name].js',
        assetFileNames: 'components-[name].[ext]',
      },
    },
  },
});
