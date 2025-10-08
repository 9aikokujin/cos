import { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/store/AuthStore/main";
import GlobalLoader from "@/ui/loader/Loader";

const AuthRedirect = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, isLoading, user } = useAuth();
  const from = location.state?.from?.pathname || "/";

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      if (user?.role === "user") {
        navigate(`/diagram/${user.id}`, { replace: true });
      } else {
        navigate(from, { replace: true });
      }
    }
  }, [isAuthenticated, isLoading, navigate, from]);

  if (isLoading) return <GlobalLoader />;

  return isAuthenticated ? null : children;
};

export default AuthRedirect;
