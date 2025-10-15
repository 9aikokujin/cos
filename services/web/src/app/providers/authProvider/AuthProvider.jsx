import { useEffect, useLayoutEffect, useState } from "react";
import { initData } from "@telegram-apps/sdk-react";

import { useAuthStore } from "@/app/store/user/store";
import Loader from "@/components/loader/Loader";

export const AuthProvider = ({ children }) => {
  const { authTG, setToken } = useAuthStore();
  const [isReady, setIsReady] = useState(false);

  // useLayoutEffect(() => {
  //   setToken(initData.raw());
  //   console.log(initData.raw());
  //   authTG(initData.raw(), initData.user());
  //   // authTG();
  //   // setToken("token");
  // }, []);
  useLayoutEffect(() => {
    try {
      const rawData = initData.raw();
      const userData = initData.user();

      if (rawData) {
        setToken(rawData);
        authTG(rawData, userData);
      }

      setIsReady(true);
    } catch (err) {
      console.error("Ошибка инициализации Telegram SDK:", err);
      setIsReady(true);
    }
  }, []);

  if (!isReady) {
    return <Loader />;
  }

  return <>{children}</>;
};
