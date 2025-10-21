const StatisticBlock = ({ title, value }) => {
  return (
    <div className="statistic_block _flex_col">
      <h3 className="_title">{title}</h3>
      <p className="_value">{value}</p>
    </div>
  );
};

export default StatisticBlock;
