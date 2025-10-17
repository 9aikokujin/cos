import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useFilterStore } from "@/app/store/filter/store";

export const useResetFiltersOnLeave = () => {
  const { pathname } = useLocation();
  const resetFilter = useFilterStore((s) => s.resetFilter);

  useEffect(() => {
    return () => {
      resetFilter();
    };
  }, [pathname]);
};
