import { parseShortNumber } from "@/shared/utils/formatString";

const StatisticBlock = ({ title, value, onClick, active }) => {
  return (
    <div onClick={onClick} className={`statistic_block _flex_col ${active ? "_active" : ""}`}>
      <h3 className="_title">{title}</h3>
      <p className="_value">{parseShortNumber(value)}</p>
    </div>
  );
};

export default StatisticBlock;
