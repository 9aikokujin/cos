import { defineConfig } from "vite";
import path from "path";
import svgr from "vite-plugin-svgr";
import react from "@vitejs/plugin-react-swc";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), svgr()],
  server: {
    host: true,
    allowedHosts: ["stupid-points-mix.loca.lt"],
  },
  resolve: {
    alias: {
      "@": path.resolve("./src"),
    },
  },
});
