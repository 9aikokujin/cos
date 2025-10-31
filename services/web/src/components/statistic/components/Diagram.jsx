import { useState } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";

import { Line } from "react-chartjs-2";

import { useFilterStore } from "@/app/store/filter/store";

import { useChartData } from "@/hooks/useChartData";
import { options } from "@/shared/utils/chartsSettings";
import Checkbox from "@/shared/ui/checkbox/Checkbox";
import { AGGREGATION_OPTIONS } from "@/shared/utils/chartsSettings";
import dayjs from "dayjs";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const Diagram = ({ data, selectedMetrics }) => {
  const { statistic, publushedVideo } = data;
  const setWithTags = useFilterStore((s) => s.setWithTags);
  const withTags = useFilterStore((s) => s.withTags);
  const filter = useFilterStore((s) => s.filter);

  const userFromDate = dayjs(filter.date_from).format("YYYY-MM-DD");

  const [aggregation, setAggregation] = useState("day");

  const { labels, datasets } = useChartData(
    statistic,
    publushedVideo,
    selectedMetrics,
    aggregation,
    userFromDate
  );

  const chartData = { labels, datasets };

  const handleAggregationChange = (value) => {
    setAggregation(value);
  };

  return (
    <>
      <div className="aggregation_container _flex">
        {AGGREGATION_OPTIONS.map((option) => (
          <Checkbox
            key={option.value}
            label={option.label}
            checked={aggregation === option.value}
            onChange={() => handleAggregationChange(option.value)}
          />
        ))}
        <Checkbox label={"С тегами"} checked={withTags} onChange={setWithTags} />
      </div>
      <div className="diagram__container">
        {selectedMetrics.length > 0 ? (
          <Line data={chartData} options={options} />
        ) : (
          <p
            className="_flex_center"
            style={{ textAlign: "center", padding: "2rem", height: "100%" }}
          >
            Выберите метрики, чтобы отобразить графики 📊
          </p>
        )}
      </div>
    </>
  );
};

export default Diagram;
