import { defineConfig } from 'vite'
import path, { dirname } from 'path';
import svgr from 'vite-plugin-svgr';
import react from '@vitejs/plugin-react-swc'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), svgr()],
  server: {
    host: true,
    allowedHosts: ["ad79d6337a5f70.lhr.life"],
  },
  resolve: {
    alias: {
      "@": path.resolve("./src"),
    },
  },
})
