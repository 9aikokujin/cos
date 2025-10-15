import { Navigate } from "react-router-dom";

import AuthForm from "@/components/authForm/AuthForm";
import { useAuthStore } from "@/app/store/user/store";

const AuthPage = () => {
  // const { isAuthenticated } = useAuthStore();
  // if (isAuthenticated) return <Navigate to={"/"} />;
  return (
    <>
      <AuthForm />
    </>
  );
};

export default AuthPage;
