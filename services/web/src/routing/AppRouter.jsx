import { memo } from "react";
import { useLocation, useRoutes } from "react-router-dom";
import { routesConfig } from "./routerConfig";

const AppRouter = memo(() => {
  console.log(useLocation());
  return useRoutes(routesConfig());
});

export default AppRouter;
