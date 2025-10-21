import { defineConfig } from 'vite'
import path, { dirname } from 'path';
import svgr from 'vite-plugin-svgr';
import react from '@vitejs/plugin-react-swc'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), svgr()],
  server: {
    host: true,
    allowedHosts: ["2ce55c9f33b53355b77fe7491a85776f.serveo.net"],
  },
  resolve: {
    alias: {
      "@": path.resolve("./src"),
    },
  },
})
