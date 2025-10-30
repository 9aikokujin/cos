import { useEffect, useState } from "react";
import { useLocation, useParams } from "react-router-dom";

import { useFilterStore } from "@/app/store/filter/store";
import { useResetFiltersOnLeave } from "@/hooks/useResetFiltersOnLeave";

import Filter from "@/components/filter/Filter";
import { Button } from "@/shared/ui/button/Button";
import Statistic from "@/components/statistic/Statistic";
import ReportBlock from "@/components/statistic/components/ReportBlock";

const StatisticPage = () => {
  const location = useLocation();
  const { filter, setFilterUserId, setFilterChannelId, setFilterVideoId } = useFilterStore();
  const [isReport, setIsReport] = useState(false);
  const { filterKey, value } = location.state || {};
  const [isLoading, setIsLoading] = useState(true);

  const { id } = useParams();
  const setUserId = useFilterStore((state) => state.setFilterUserId);

  useEffect(() => {
    if (!id) return;
    setUserId(id);
  }, [id]);

  useEffect(() => {
    if (filterKey && value !== undefined) {
      const actionMap = {
        setFilterUserId,
        setFilterChannelId,
        setFilterVideoId,
      };
      actionMap[filterKey](value);
    }
    setIsLoading(false);
  }, [filterKey, value]);

  useResetFiltersOnLeave();

  const handleReport = () => {
    setIsReport((prev) => !prev);
  };
  return isLoading ? (
    <></>
  ) : (
    <div className="container" style={{ overflow: "auto" }}>
      <div className="_flex_sb" style={{ gap: 11, marginBottom: 12 }}>
        <Filter />
        <Button className={`_white ${isReport && "_active"} report_btn`} onClick={handleReport}>
          Отчет
        </Button>
      </div>
      <Statistic />
      {isReport && <ReportBlock />}
    </div>
  );
};

export default StatisticPage;
