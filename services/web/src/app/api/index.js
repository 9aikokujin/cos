import axios from "axios";
import auth from "./auth";
import user from "./user";
import account from "./account";
import video from "./video";

import { useAuthStore } from "../store/user/store";
import { useNotificationStore } from "../store/notification/store";

export const instance = axios.create({
  baseURL: "https://cosmeya.dev-klick.cyou/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

// export const instanceFormData = axios.create({
//   baseURL: "https://sn.dev-klick.cyou/api/v1",
//   headers: {},
// });

instance.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

instance.interceptors.response.use(
  (response) => response,
  (error) => {
    const ui = useNotificationStore.getState();

    // Сервер ответил с ошибкой
    if (error.response) {
      const status = error.response.status;

      switch (status) {
        case 400:
          ui.showNotification("Некорректный запрос. Проверьте данные.");
          break;
        case 401:
          ui.showNotification("Необходима авторизация.");
          // Можно вызвать logout или редирект
          useAuthStore.getState().logout?.();
          break;
        case 403:
          ui.showNotification("Нет доступа к ресурсу.");
          break;
        case 404:
          ui.showNotification("Ресурс не найден.");
          break;
        case 500:
          ui.showNotification("Ошибка сервера. Попробуйте позже.");
          break;
        default:
          ui.showNotification(`Ошибка: ${error.response.data?.message || "Неизвестная ошибка"}`);
      }
    } else if (error.request) {
      ui.showNotification("Сервер не отвечает. Проверьте соединение.");
    } else {
      ui.showNotification(`Ошибка: ${error.message}`);
    }

    return Promise.reject(error);
  }
);

const API = {
  auth: auth(instance),
  user: user(instance),
  account: account(instance),
  video: video(instance),
};

export default API;
