import { useRoutes, Navigate } from "react-router-dom";

import { AppRoutes, getRoutesByRole } from "./routes";
import { PrivateRoute } from "./PrivatesRoute";

import { useAuthStore } from "../store/user/store";
import { useMemo } from "react";

export const useAppRouterConfig = () => {
  const { isAuthenticated, user } = useAuthStore();

  const routes = getRoutesByRole(user?.role, user?.id, isAuthenticated);

  const defaultRoute =
    user?.role === "admin" ? AppRoutes.ACCOUNTS : AppRoutes.VIDEOS_USER.replace(":id", user?.id);

  // Формируем дерево маршрутов (RouteObject[])
  return useMemo(
    () => [
      {
        path: "/",
        element: isAuthenticated ? (
          <Navigate to={defaultRoute} replace />
        ) : (
          <Navigate to={AppRoutes.AUTH} replace />
        ),
      },
      {
        element: (
          <PrivateRoute
            isAuth={isAuthenticated}
            id={user?.id}
            userRole={user?.role || "user"}
            allowedRoles={["admin", "user"]}
          />
        ),
        children: routes.filter(
          (r) => r.path !== AppRoutes.AUTH && r.path !== AppRoutes.NOT_FOUND
        ),
      },
      ...routes.filter((r) => r.path === AppRoutes.AUTH || r.path === AppRoutes.NOT_FOUND),
    ],
    [isAuthenticated]
  );
};
