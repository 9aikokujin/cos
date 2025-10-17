import Filter from "@/components/filter/Filter";
import { useFilterStore } from "@/app/store/filter/store";
import { useResetFiltersOnLeave } from "@/hooks/useResetFiltersOnLeave";

const StatisticPage = () => {
  const { filter } = useFilterStore();
  console.log(filter);
  useResetFiltersOnLeave()
  return (
    <div className="container">
      <div className="_flex_sb" style={{ gap: 11, marginBottom: 12 }}>
        <Filter />
      </div>
    </div>
  );
};

export default StatisticPage;
