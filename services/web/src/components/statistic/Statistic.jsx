import { useEffect, useState } from "react";

import API from "@/app/api";
import { useFilterStore } from "@/app/store/filter/store";
import { sumFields } from "@/shared/utils/utils";

import Loader from "@/components/loader/Loader";
import Diagram from "./components/Diagram";
import ReportBlock from "./components/ReportBlock";
import StatisticBlock from "./components/StatisticBlock";

import "./Statistic.css";

const Statistic = () => {
  const { filter, withTags, isLoading, tag } = useFilterStore();
  const [statistic, setStatistic] = useState([]);
  const [publushedVideo, setPublishedVideo] = useState([]);

  useEffect(() => {
    const clean = (obj) =>
      Object.fromEntries(
        Object.entries(obj).filter(([_, v]) => v !== "" && v !== null && v !== undefined)
      );

    const getStatistic = async () => {
      if (withTags) {
        const data = await API.statistic.getStatisticWithTags({
          articles: clean(tag),
          ...clean(filter),
        });
        const published = await API.statistic.getCountPublishedVideoWithTags({
          ...clean(filter),
        });
        setPublishedVideo(published);
        setStatistic(data);
      } else {
        const data = await API.statistic.getStatistic(clean(filter));
        const published = await API.statistic.getCountPublishedVideo({
          ...clean(filter),
        });
        setPublishedVideo(published);
        setStatistic(data);
      }
    };
    getStatistic();
  }, [filter, withTags]);
  return (
    <>
      <div className="statistic_container">
        <StatisticBlock title="Просмотры" value={sumFields(statistic, ["views"]).views} />
        <StatisticBlock
          title="Публикации"
          value={sumFields(publushedVideo, ["video_count"]).video_count}
        />
        <StatisticBlock title="Комментарии" value={sumFields(statistic, ["comments"]).comments} />
        <StatisticBlock title="Лайки" value={sumFields(statistic, ["likes"]).likes} />
      </div>
      <Diagram />
      <ReportBlock />
      {isLoading && <Loader />}
    </>
  );
};

export default Statistic;
