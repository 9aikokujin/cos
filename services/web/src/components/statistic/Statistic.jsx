import Diagram from "./components/Diagram";
import ReportBlock from "./components/ReportBlock";
import StatisticBlock from "./components/StatisticBlock";

import "./Statistic.css";

const Statistic = () => {
  return (
    <>
      <div className="statistic_container">
        <StatisticBlock title="Просмотры" value="120" />
        <StatisticBlock title="Публикации" value="120" />
        <StatisticBlock title="Комментарии" value="120" />
        <StatisticBlock title="Лайки" value="120" />
      </div>
      <Diagram />
      <ReportBlock />
    </>
  );
};

export default Statistic;
