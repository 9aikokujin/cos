import { Navigate, Outlet } from "react-router-dom";
import { AppRoutes } from "./routes";


// 🔒 Если пользователь авторизован — рендерим дочерние роуты
// иначе — редирект на /auth
export const PrivateRoute = ({
  isAuth,
  userRole,
  allowedRoles = ["admin", "user"],
  redirectPath = AppRoutes.AUTH,
}) => {
  if (!isAuth) {
    return <Navigate to={redirectPath} replace />;
  }
  if (!allowedRoles.includes(userRole)) {
    // Если роль не разрешена → перенаправляем на страницу 404 или статистики, например
    return <Navigate to={AppRoutes.VIDEOS_USER} replace />;
  }

  return <Outlet />;
};
