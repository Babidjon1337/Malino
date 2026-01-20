import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    allowedHosts: [
      ".lhr.life",
      ".ru.tuna.am",
      "localhost",
      ".serveo.net",
      ".ngrok.io",
      ".ngrok-free.app",
    ],
  },
  build: {
    // !!! ВОТ ЭТА СТРОКА ЧИНИТ СЕРЫЙ ЭКРАН НА ТЕЛЕФОНЕ !!!
    target: "es2020",
    outDir: "dist",
    assetsDir: "assets",
  },
});
