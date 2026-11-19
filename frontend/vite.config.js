import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/redteam': 'http://localhost:8000',
      '/verify': 'http://localhost:8000',
      '/report': 'http://localhost:8000',
      '/claims': 'http://localhost:8000',
      '/demo': 'http://localhost:8000',
      '/audit': 'http://localhost:8000',
      '/benchmark': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
});
