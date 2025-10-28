import { matchPath, useLocation } from "react-router-dom";

import { AppRoutes } from "../app/routes/routes";
import { filters } from "../shared/utils/filters";
import { useFilterStore } from "../app/store/filter/store";

const pageFiltersByPath = {
  [AppRoutes.VIDEOS]: ["users", "social"],
  [AppRoutes.VIDEOS_USER]: ["social"],
  [AppRoutes.USER]: [],
  [AppRoutes.ACCOUNTS]: ["social"],
  [AppRoutes.STATISTIC]: ["date", "users", "accounts", "social", "tags"],
  [AppRoutes.STATISTIC_USER]: ["date", "accounts", "social", "tags"],
};

const filtersMap = Object.fromEntries(filters.map((f) => [f.id, f]));

const getStatisticExclusions = (filter, withTags) => {
  const exclusions = [];

  if (filter.user_ids) {
    exclusions.push("accounts");
  }
  if (filter.channel_id) {
    exclusions.push("users", "social");
  }
  if (filter.video_id) {
    exclusions.push("social", "accounts", "users");
  }

  if (!withTags) {
    exclusions.push("tags");
  }

  return exclusions;
};

export const usePageFilters = () => {
  const { pathname } = useLocation();
  const { filter, withTags } = useFilterStore();

  const matchedPath = Object.keys(pageFiltersByPath).find((route) =>
    matchPath({ path: route, end: true }, pathname)
  );

  const filterIds = matchedPath ? pageFiltersByPath[matchedPath] : [];

  let finalFilterIds = [...filterIds];

  if (matchedPath === AppRoutes.STATISTIC || matchedPath === AppRoutes.STATISTIC_USER) {
    const excludedFilters = getStatisticExclusions(filter, withTags);
    finalFilterIds = filterIds.filter((id) => !excludedFilters.includes(id));
  }

  return finalFilterIds.map((id) => filtersMap[id]).filter(Boolean);
};
