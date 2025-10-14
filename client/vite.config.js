import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0", // Разрешить доступ со всех адресов
    port: 5173, // Порт приложения
    strictPort: true, // Не искать свободные порты
    allowedHosts: [
      // Разрешенные хосты
      ".lhr.life",
      ".ru.tuna.am",
      "localhost",
      ".serveo.net", // Разрешить все поддомены serveo.net
      ".ngrok.io", // Разрешить все поддомены ngrok.io
      ".ngrok-free.app", // Для нового ngrok
    ],
  },
  build: {
    outDir: "dist",
    assetsDir: "assets",
  },
});
