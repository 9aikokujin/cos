import { useEffect, useState } from "react";
import dayjs from "dayjs";

import { useFiltersModalStore } from "@/app/store/filterModal/store";
import { useFilterStore } from "@/app/store/filter/store";

import { ComponentIcon } from "@/shared/ui/icon/ComponentIcon";
import { datePeriods } from "@/shared/utils/filters";
import { DatePicker } from "@/shared/ui/dataPicker/DatePicker";

const DateFilter = () => {
  const { setFooter, close, push } = useFiltersModalStore();
  const [selectedPeriod, setSelectedPeriod] = useState(null);
  const setDateFrom = useFilterStore((state) => state.setFilterDateFrom);
  const setDateTo = useFilterStore((state) => state.setFilterDateTo);

  const handleSelectPeriod = () => {
    if (!selectedPeriod) return;
    setDateFrom(dayjs(selectedPeriod.date_from).format("YYYY-MM-DD"));
    setDateTo(dayjs(selectedPeriod.date_to).format("YYYY-MM-DD"));
    close();
  };

  useEffect(() => {
    setFooter({
      text: "Применить",
      visible: true,
      onClick: handleSelectPeriod,
    });
  }, [selectedPeriod]);

  const handleOpenCustomRange = () => {
    push({ id: "date_custom", component: DatePicker });
  };
  return (
    <div className="date_filter _flex_col_center" style={{ gap: 10 }}>
      <button className="date_calendar_btn _flex_center" onClick={handleOpenCustomRange}>
        <ComponentIcon name={"calendar"} />
      </button>
      {datePeriods.map((period, index) => (
        <div
          key={index}
          onClick={() => setSelectedPeriod(period)}
          className={`filter_item ${selectedPeriod === period ? "_active" : ""}`}
        >
          {period.title}
        </div>
      ))}
    </div>
  );
};

export default DateFilter;
