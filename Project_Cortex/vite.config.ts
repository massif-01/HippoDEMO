import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    proxy: {
      '/recording-api': {
        target: 'https://vlmac.xapp.aoseo.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/recording-api/, '/api'),
        secure: true
      },
      '/minio-api': {
        target: 'http://171.88.165.251:59000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/minio-api/, '')
      },
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    // Enable minification for production
    minify: 'esbuild',
    // Generate source maps for debugging but not in production
    sourcemap: false,
    // Chunk splitting for better caching
    rollupOptions: {
      output: {
        manualChunks: {
          // Split vendor chunks for better caching
          'marked': ['marked']
        }
      }
    },
    // Target modern browsers for smaller bundles
    target: 'es2020'
  },
  optimizeDeps: {
    // Pre-bundle dependencies for faster dev startup
    include: ['marked', 'svelte/easing']
  },
  // Improve CSS handling
  css: {
    devSourcemap: true
  }
});
