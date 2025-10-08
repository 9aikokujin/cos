const StatisticBlock = ({ name, count }) => {
  return (
    <>
      <div className="statistic__block _flex_column_center">
        <div className="statistic__count _flex_center">
          <p>{count}</p>
        </div>
        <div className="statistic__name _flex_center">
          <p>{name}</p>
        </div>
      </div>
    </>
  );
};

export default StatisticBlock;
