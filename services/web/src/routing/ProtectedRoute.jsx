// import { useEffect } from 'react';
// import { useNavigate, useLocation } from 'react-router-dom';
// import { useAuth } from '@/store/AuthStore/main';

// const ProtectedRoute = ({ children }) => {
//   const navigate = useNavigate();
//   const location = useLocation();
//   const { isAuthenticated, isLoading } = useAuth();

//   useEffect(() => {
//     if (!isLoading && !isAuthenticated && !location.pathname.startsWith('/auth')) {
//       navigate('/auth/register', {
//         state: { from: location },
//         replace: true
//       });
//     }
//   }, [isAuthenticated, isLoading, navigate, location]);

//   if (isLoading) return <div>Loading...</div>;

//   return isAuthenticated ? children : null;
// };

// export default ProtectedRoute;

// import { useEffect } from "react";
// import { useNavigate, useLocation } from "react-router-dom";
// import { useAuth } from "@/store/AuthStore/main";

// const ProtectedRoute = ({ children, allowedRoles = [], redirectPath = "/auth/register" }) => {
//   const navigate = useNavigate();
//   const location = useLocation();
//   const { isAuthenticated, isLoading, user } = useAuth();

//   useEffect(() => {
//     if (isLoading) return;

//     if (!isAuthenticated && !location.pathname.startsWith("/auth")) {
//       navigate(redirectPath, {
//         state: { from: location },
//         replace: true,
//       });
//       return;
//     }

//     if (isAuthenticated && allowedRoles.length > 0 && !allowedRoles.includes(user?.role)) {
//       const redirectTo = user?.role === "user" ? `/diagram/${user.id}` : "/";
//       navigate(redirectTo, { replace: true });
//     }
//   }, [isAuthenticated, isLoading, navigate, location, user, allowedRoles, redirectPath]);

//   if (isLoading) return <div>Loading...</div>;

//   const hasAccess =
//     isAuthenticated && (allowedRoles.length === 0 || allowedRoles.includes(user?.role));

//   return hasAccess ? children : null;
// };

// export default ProtectedRoute;

import { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/store/AuthStore/main";
import GlobalLoader from "@/ui/loader/Loader";

const ProtectedRoute = ({
  children,
  allowedRoles = [],
  redirectPath = "/auth/register",
  blockedUserPath = "/block",
}) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, isLoading, user } = useAuth();

  useEffect(() => {
    if (isLoading) return;

    if (user?.is_blocked) {
      navigate(blockedUserPath, { replace: true });
      return;
    }

    if (!isAuthenticated && !location.pathname.startsWith("/auth")) {
      navigate(redirectPath, {
        state: { from: location },
        replace: true,
      });
      return;
    }

    if (user?.role === "user" && location.pathname === "/") {
      navigate(`/diagram/${user.id}`, { replace: true });
    }

    if (isAuthenticated && allowedRoles.length > 0 && !allowedRoles.includes(user?.role)) {
      const redirectTo = user?.role === "user" ? `/diagram/${user.id}` : "/";
      navigate(redirectTo, { replace: true });
    }
  }, [isAuthenticated, isLoading, user]);

  if (isLoading) return <GlobalLoader />;

  const isBlocked = user?.is_blocked;
  const hasAccess =
    !isBlocked &&
    isAuthenticated &&
    (allowedRoles.length === 0 || allowedRoles.includes(user?.role));

  if (isBlocked) {
    navigate(blockedUserPath, { replace: true });
    return null;
  }

  return hasAccess ? children : null;
};

export default ProtectedRoute;
