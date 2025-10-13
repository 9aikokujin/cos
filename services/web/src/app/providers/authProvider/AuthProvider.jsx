import { useEffect } from "react";
// import { initData } from "@telegram-apps/sdk-react";
import { useAuthStore } from "../../store/user/store";

export const AuthProvider = ({ children }) => {
  const {authTG, setToken} = useAuthStore();

  useEffect(() => {
    // setToken(initData.raw());
    // authTG(initData.raw(), initData.user());
    authTG();
    setToken("token");
  }, []);

  return <>{children}</>;
};
