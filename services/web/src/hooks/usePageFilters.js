import { matchPath, useLocation } from "react-router-dom";

import { AppRoutes } from "../app/routes/routes";
import { filters } from "../shared/utils/filters";

const pageFiltersByPath = {
  [AppRoutes.VIDEOS]: ["users", "social"],
  [AppRoutes.VIDEOS_USER]: ["social"],
  [AppRoutes.USER]: [],
  [AppRoutes.ACCOUNTS]: ["social"],
  [AppRoutes.STATISTIC]: ["date", "users", "accounts", "social", "tags"],
  [AppRoutes.STATISTIC_USER]: ["date", "accounts", "social","tags"],
};

const filtersMap = Object.fromEntries(filters.map((f) => [f.id, f]));

export const usePageFilters = () => {
  const { pathname } = useLocation();

  const matchedPath = Object.keys(pageFiltersByPath).find((route) =>
    matchPath({ path: route, end: true }, pathname)
  );

  const filterIds = matchedPath ? pageFiltersByPath[matchedPath] : [];

  return filterIds.map((id) => filtersMap[id]).filter(Boolean);
};
