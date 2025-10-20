import { useLocation } from "react-router-dom";

import { AppRoutes } from "../app/routes/routes";
import { filters } from "../shared/utils/filters";

const pageFiltersByPath = {
  [AppRoutes.VIDEOS]: ["users", "social"],
  [AppRoutes.USER]: [],
  [AppRoutes.ACCOUNTS]: ["social"],
  [AppRoutes.STATISTIC]: ["date", "users", "accounts", "social", "tags"],
};

const filtersMap = Object.fromEntries(filters.map((f) => [f.id, f]));

export const usePageFilters = () => {
  const location = useLocation();
  const path = location.pathname;

  const matchedPath = Object.keys(pageFiltersByPath).find((key) => path.startsWith(key));

  const filterIds = matchedPath ? pageFiltersByPath[matchedPath] : [];

  return filterIds.map((id) => filtersMap[id]).filter(Boolean);
};
