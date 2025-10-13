import { useState, useEffect, useMemo } from "react";
import { useLocation, matchPath } from "react-router-dom";

export const useActiveFooterLink = (linksConfig) => {
  const location = useLocation();
  const [activeIndex, setActiveIndex] = useState(null);

  const memoizedLinks = useMemo(() => linksConfig, [linksConfig]);

  useEffect(() => {
    const currentPath = location.pathname;

    const foundIndex = memoizedLinks.findIndex((link) => {
      const match = matchPath({ path: link.path, end: !link.matchSubpaths }, currentPath);

      return Boolean(match);
    });

    setActiveIndex(foundIndex >= 0 ? foundIndex : null);
  }, [location.pathname, memoizedLinks]);

  const setActive = (index) => setActiveIndex(index);

  const isActive = (index) => (activeIndex === index ? "_active" : "");

  return { isActive, setActive, activeIndex };
};
