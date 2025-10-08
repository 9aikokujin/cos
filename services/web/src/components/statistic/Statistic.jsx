import { sumAndFormat } from "@/helpers/sumAndFormat";

import StatisticBlock from "./statisticBlock/StatisticBlock";

import "./Statistic.css";

const Statistic = ({ views }) => {
  return (
    <>
      <h3 className="statistic__title">По источникам трафика</h3>
      <div className="statistic__info">
        <StatisticBlock name={"Просмотры"} count={sumAndFormat(views)} />
        {/* <StatisticBlock name={"Хештеги"} count={"86 тыс"} /> */}
      </div>
    </>
  );
};

export default Statistic;
