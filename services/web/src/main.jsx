import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { init, initData, miniApp } from "@telegram-apps/sdk-react";

import { AppProviders } from "./app/providers/AppProviders.jsx";
import App from "./App.jsx";

import "@/assets/css/main.css";

const initializeTelegramSDK = async () => {
  try {
    await init();

    if (miniApp.ready.isAvailable()) {
      await miniApp.ready();

      initData.restore();
      initData.state();

      console.log("Mini App готово");
    }
  } catch (error) {
    console.error("Ошибка инициализации:", error);
  }
};

initializeTelegramSDK();

createRoot(document.getElementById("root")).render(
  // <StrictMode>
    <AppProviders>
      <App />
    </AppProviders>
  // </StrictMode>
);
