import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev: `npm run dev` on :5173 proxies /api to Flask on :5000. Prod: Flask serves frontend/dist.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:5000', '/ping': 'http://localhost:5000' } },
});
