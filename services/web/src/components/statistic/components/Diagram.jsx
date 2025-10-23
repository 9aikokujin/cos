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

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const COLORS = {
  views: "rgb(75, 192, 192)",
  likes: "rgb(255, 99, 132)",
  comments: "rgb(255, 206, 86)",
  video_count: "rgb(153, 102, 255)",
};

const LABELS = {
  views: "Просмотры",
  likes: "Лайки",
  comments: "Комментарии",
  video_count: "Публикации",
};

const Diagram = ({ data, selectedMetrics }) => {
  const { statistic, publushedVideo } = data;

  const labels =
    statistic.length > 0
      ? statistic.map((item) =>
          new Date(item.date).toLocaleDateString("ru-RU", { day: "2-digit", month: "short" })
        )
      : [];

  const datasets = selectedMetrics.map((metric) => {
    let values;

    if (metric === "video_count") {
      values = publushedVideo.map((item) => item.video_count ?? 0);
    } else {
      values = statistic.map((item) => item[metric] ?? 0);
    }

    return {
      label: LABELS[metric] || metric,
      data: values,
      borderColor: COLORS[metric],
      borderWidth: 1.5,
      tension: 0.3,
      pointBackgroundColor: "#fff",
      pointBorderColor: COLORS[metric],
      pointRadius: 3,
    };
  });

  const chartData = { labels, datasets };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: "bottom",
        align: "start",
        labels: {
          pointStyle: "circle", 
          boxWidth: 10,        
          boxHeight: 9, 
          padding: 20,
          usePointStyle: true,
          font: { size: 13 },
        },
      },
      tooltip: {
        mode: "index",
        intersect: false,
      },
    },
    layout: {
      padding: { bottom: 20 },
    },
  };

  return (
    <div className="diagram__container">
      {selectedMetrics.length > 0 ? (
        <Line data={chartData} options={options} />
      ) : (
        <p style={{ textAlign: "center", padding: "2rem" }}>
          Выберите метрики, чтобы отобразить графики 📊
        </p>
      )}
    </div>
  );
};

export default Diagram;