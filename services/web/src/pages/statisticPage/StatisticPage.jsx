import { useFilterStore } from "@/app/store/filter/store";
import { useResetFiltersOnLeave } from "@/hooks/useResetFiltersOnLeave";

import Filter from "@/components/filter/Filter";
import Statistic from "@/components/statistic/Statistic";

const StatisticPage = () => {
  const { filter } = useFilterStore();
  console.log(filter);
  useResetFiltersOnLeave();
  return (
    <div className="container" style={{overflow: "auto"}}>
      <div className="_flex_sb" style={{ gap: 11, marginBottom: 12 }}>
        <Filter />
      </div>
      <Statistic />
    </div>
  );
};

export default StatisticPage;
