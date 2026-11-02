import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Os arquivos gerados são servidos pelo FastAPI em /static/app/ (mesma origem da API: o login por
// cookie continua igual, sem CORS). OUT_DIR é definido pelo Compose (e pelo Dockerfile de produção).
export default defineConfig({
  base: "/static/app/",
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  build: {
    outDir: process.env.OUT_DIR ?? "dist",
    emptyOutDir: true,
    chunkSizeWarningLimit: 1200, // o ECharts sozinho passa de 500 kB
  },
});
