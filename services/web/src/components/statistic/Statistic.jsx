import { useEffect, useState } from "react";

import API from "@/app/api";
import { useFilterStore } from "@/app/store/filter/store";
import { sumFields, sumVideoCounts } from "@/shared/utils/utils";

import Loader from "@/components/loader/Loader";
import Diagram from "./components/Diagram";
import StatisticBlock from "./components/StatisticBlock";

import "./Statistic.css";
import dayjs from "dayjs";

const Statistic = () => {
  const { filter, withTags, isLoading, tag } = useFilterStore();
  const [statistic, setStatistic] = useState([]);
  const [publushedVideo, setPublishedVideo] = useState([]);
  const [selectedMetrics, setSelectedMetrics] = useState([]);

  useEffect(() => {
    const clean = (obj) =>
      Object.fromEntries(
        Object.entries(obj).filter(([_, v]) => v !== "" && v !== null && v !== undefined)
      );

    const getStatistic = async () => {
      const patchedFilter = {
        ...clean(filter),
        date_from: filter.date_from
          ? dayjs(filter.date_from).subtract(1, "day").format("YYYY-MM-DD")
          : undefined,
      };
      console.log(patchedFilter);

      if (withTags) {
        const data = await API.statistic.getStatisticWithTags({
          ...patchedFilter,
          articles: tag,
        });
        const published = await API.statistic.getCountPublishedVideoWithTags({
          ...clean(filter), articles: tag,
        });
        setPublishedVideo(published);
        setStatistic(data);
      } else {
        const data = await API.statistic.getStatistic(patchedFilter);
        const published = await API.statistic.getCountPublishedVideo({
          ...clean(filter),
        });
        setPublishedVideo(published);
        setStatistic(data);
      }
    };
    getStatistic();
  }, [filter, withTags, tag]);

  

  const toggleMetric = (metric) => {
    setSelectedMetrics((prev) =>
      prev.includes(metric) ? prev.filter((m) => m !== metric) : [...prev, metric]
    );
  };

  return (
    <>
      <div className="statistic_container">
        <StatisticBlock
          title="Просмотры"
          value={sumFields(statistic, ["views"]).views}
          onClick={() => toggleMetric("views")}
          active={selectedMetrics.includes("views")}
        />
        {!filter.video_id && (
          <StatisticBlock
            title="Публикации"
            value={sumVideoCounts(publushedVideo, ["video_count"]).video_count}
            onClick={() => toggleMetric("video_count")}
            active={selectedMetrics.includes("video_count")}
          />
        )}
        <StatisticBlock
          title="Комментарии"
          value={sumFields(statistic, ["comments"]).comments}
          onClick={() => toggleMetric("comments")}
          active={selectedMetrics.includes("comments")}
        />
        <StatisticBlock
          title="Лайки"
          value={sumFields(statistic, ["likes"]).likes}
          onClick={() => toggleMetric("likes")}
          active={selectedMetrics.includes("likes")}
        />
      </div>
      <Diagram data={{ statistic, publushedVideo }} selectedMetrics={selectedMetrics} />
      {isLoading && <Loader />}
    </>
  );
};

export default Statistic;
