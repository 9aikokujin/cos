// import { useMemo } from "react";

// import { COLORS, LABELS } from "@/shared/utils/chartsSettings";

// const formatDate = (date, aggregation) => {
//   const d = new Date(date);
//   switch (aggregation) {
//     case "day":
//       return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "short" });
//     case "week": {
//       // неделя: ISO week start (понедельник)
//       const day = d.getDay() || 7; // воскресенье -> 7
//       const monday = new Date(d);
//       monday.setDate(d.getDate() - day + 1);
//       return monday.toLocaleDateString("ru-RU", { day: "2-digit", month: "short" });
//     }
//     case "month":
//       return d.toLocaleString("ru-RU", { month: "short", year: "numeric" });
//     default:
//       return d.toLocaleDateString();
//   }
// };

// const getKey = (date, aggregation) => {
//   const d = new Date(date);
//   switch (aggregation) {
//     case "day":
//       return d.toISOString().split("T")[0]; // YYYY-MM-DD
//     case "week": {
//       const day = d.getDay() || 7;
//       const monday = new Date(d);
//       monday.setDate(d.getDate() - day + 1);
//       return monday.toISOString().split("T")[0];
//     }
//     case "month":
//       return d.getFullYear() * 100 + (d.getMonth() + 1); // YYYYMM
//     default:
//       return d.toISOString();
//   }
// };

// export const useChartData = (
//   statistic = [],
//   publushedVideo = [],
//   selectedMetrics = [],
//   aggregation = "day"
// ) => {
//   return useMemo(() => {
//     let allData = [...statistic];

//     // Добавляем publushedVideo только если выбран metric video_count
//     if (selectedMetrics.includes("video_count")) {
//       allData = [...allData, ...publushedVideo];
//     }
//     const allKeys = Array.from(
//       new Set(
//         allData.map((item) =>
//           getKey(item.date ?? item.date_published ?? item.date_published_from, aggregation)
//         )
//       )
//     );

//     // Сортируем
//     const sortedKeys = allKeys.sort((a, b) => {
//       if (aggregation === "month") return a - b; // числовая сортировка YYYYMM
//       return new Date(a) - new Date(b);
//     });

//     const labels = sortedKeys.map((key) => {
//       if (aggregation === "month") {
//         const year = Math.floor(key / 100);
//         const month = (key % 100) - 1;
//         return new Date(year, month).toLocaleString("ru-RU", { month: "short", year: "numeric" });
//       }
//       return new Date(key).toLocaleDateString("ru-RU", { day: "2-digit", month: "short" });
//     });

//     const datasets = selectedMetrics.map((metric) => {
//       const values = sortedKeys.map((key) => {
//         if (metric === "video_count") {
//           const item = publushedVideo.find(
//             (v) => getKey(v.date ?? v.date_published ?? v.date_published_from, aggregation) === key
//           );
//           return item?.video_count ?? 0;
//         } else {
//           const item = statistic.find(
//             (s) => getKey(s.date ?? s.date_published ?? s.date_published_from, aggregation) === key
//           );
//           return item?.[metric] ?? 0;
//         }
//       });

//       return {
//         label: LABELS[metric] || metric,
//         data: values,
//         borderColor: COLORS[metric],
//         borderWidth: 1.5,
//         tension: 0.3,
//         pointBackgroundColor: "#fff",
//         pointBorderColor: COLORS[metric],
//         pointRadius: 3,
//       };
//     });

//     return { labels, datasets };
//   }, [statistic, publushedVideo, selectedMetrics, aggregation]);
// };


import { useMemo } from "react";
import { COLORS, LABELS } from "@/shared/utils/chartsSettings";

const formatDate = (date, aggregation) => {
  const d = new Date(date);
  switch (aggregation) {
    case "day":
      return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "short" });
    case "week": {
      const day = d.getDay() || 7;
      const monday = new Date(d);
      monday.setDate(d.getDate() - day + 1);
      return monday.toLocaleDateString("ru-RU", { day: "2-digit", month: "short" });
    }
    case "month":
      return d.toLocaleString("ru-RU", { month: "short", year: "numeric" });
    default:
      return d.toLocaleDateString();
  }
};

const getKey = (date, aggregation) => {
  const d = new Date(date);
  switch (aggregation) {
    case "day":
      return d.toISOString().split("T")[0];
    case "week": {
      const day = d.getDay() || 7;
      const monday = new Date(d);
      monday.setDate(d.getDate() - day + 1);
      return monday.toISOString().split("T")[0];
    }
    case "month":
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    default:
      return d.toISOString();
  }
};

export const useChartData = (
  statistic = [],
  publushedVideo = [],
  selectedMetrics = [],
  aggregation = "day"
) => {
  return useMemo(() => {
    let allData = [...statistic];
    if (selectedMetrics.includes("video_count")) {
      allData = [...allData, ...publushedVideo];
    }

    // === Группировка по ключам ===
    const grouped = {};

    allData.forEach((item) => {
      const date = item.date ?? item.date_published ?? item.date_published_from;
      const key = getKey(date, aggregation);

      if (!grouped[key]) grouped[key] = [];

      grouped[key].push(item);
    });

    // === Получаем отсортированные ключи ===
    const sortedKeys = Object.keys(grouped).sort((a, b) => {
      if (aggregation === "month") return new Date(a) - new Date(b);
      return new Date(a) - new Date(b);
    });

    // === Метки для оси X ===
    const labels = sortedKeys.map((key) => formatDate(key, aggregation));

    // === Формируем datasets ===
    const datasets = selectedMetrics.map((metric) => {
      const values = sortedKeys.map((key) => {
        const items = grouped[key];

        // Суммируем значения по этому периоду
        const total = items.reduce((sum, item) => {
          if (metric === "video_count") return sum + (item.video_count ?? 0);
          return sum + (item[metric] ?? 0);
        }, 0);

        return total;
      });

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

    return { labels, datasets };
  }, [statistic, publushedVideo, selectedMetrics, aggregation]);
};
