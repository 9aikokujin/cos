import { useEffect, useState } from "react";

import { AnaliticAPI } from "@/api";
import { useFilter } from "@/store/FilterAnalitic/main";

export const useStatisticData = (id) => {
  const [viewsArray, setViewsArray] = useState([]);
  const [date, setDate] = useState([]);
  const { filter } = useFilter();

  const getSeparatedArrays = (data) => {
    if (!Array.isArray(data)) {
      return { dates: [], views: [] };
    }

    const dates = [];
    const views = [];

    data.forEach((item) => {
      if (item.day) dates.push(item.day);
      if (item.total_views) views.push(item.total_views);
    });

    return { dates, views };
  };

  useEffect(() => {
    const fetchStatistic = async () => {
      const res = await AnaliticAPI.statistic.getStatisctic({
        ...filter,
        id: id ? id : null,
      });
      const { dates, views } = getSeparatedArrays(res);
      setViewsArray(views);
      setDate(dates);
    };

    fetchStatistic();
  }, [filter]);

  return { viewsArray, date };
};
