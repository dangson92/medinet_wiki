import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

// Dev-only API proxy đích — uvicorn central (memory `project_run_backend_local`).
// Production qua Caddy reverse proxy (Phase 5 PROXY-01), KHÔNG đụng config này.
const API_PROXY_TARGET = process.env.VITE_API_PROXY ?? 'http://localhost:8080';

export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      hmr: process.env.DISABLE_HMR !== 'true',
      proxy: {
        // Central API + JWKS — forward thẳng tới uvicorn.
        '/api': { target: API_PROXY_TARGET, changeOrigin: true },
        '/.well-known': { target: API_PROXY_TARGET, changeOrigin: true },
        // Hub-con subpath — strip `/<hub>` prefix (mimic Caddy Plan 05-01)
        // để local dev test luồng hub-prefix mà chỉ chạy central.
        '^/(yte|duoc|hcns|dmd|tdt)/api': {
          target: API_PROXY_TARGET,
          changeOrigin: true,
          rewrite: (urlPath) => urlPath.replace(/^\/(yte|duoc|hcns|dmd|tdt)/, ''),
        },
      },
    },
  };
});
