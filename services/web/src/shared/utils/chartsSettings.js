export const COLORS = {
  views: "rgb(75, 192, 192)",
  likes: "rgb(255, 99, 132)",
  comments: "rgb(255, 206, 86)",
  video_count: "rgb(153, 102, 255)",
};

export const LABELS = {
  views: "Просмотры",
  likes: "Лайки",
  comments: "Комментарии",
  video_count: "Публикации",
};

export const AGGREGATION_OPTIONS = [
  { label: "День", value: "day" },
  { label: "Неделя", value: "week" },
  { label: "Месяц", value: "month" },
];

// export const options = {
//   responsive: true,
//   maintainAspectRatio: false,
//   plugins: {
//     legend: {
//       display: true,
//       position: "bottom",
//       align: "start",
//       labels: {
//         pointStyle: "circle",
//         boxWidth: 10,
//         boxHeight: 9,
//         padding: 20,
//         usePointStyle: true,
//         font: { size: 13 },
//       },
//     },
//     tooltip: {
//       mode: "index",
//       intersect: false,
//     },
//   },
//   layout: {
//     padding: { bottom: 20 },
//   },
// };

export const options = {
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
      callbacks: {
        // Здесь формируем tooltip с двумя строками: прирост и абсолютное значение
        label: function (context) {
          const dataset = context.dataset;
          const growth = dataset.data[context.dataIndex];
          const total = dataset.originalTotals[context.dataIndex];
          // Если video_count, показываем только абсолютное значение
          if (dataset.label === LABELS["video_count"]) {
            return `${dataset.label}: ${total}`;
          }
          return [`Прирост: ${growth}`, `${dataset.label}: ${total}`];
        },
      },
    },
  },
  layout: {
    padding: { bottom: 20 },
  },
};
