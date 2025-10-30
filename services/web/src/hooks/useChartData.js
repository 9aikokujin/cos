// import { useMemo } from "react";
// import { COLORS, LABELS } from "@/shared/utils/chartsSettings";

// // Форматирование меток оси X
// const formatDate = (date, aggregation) => {
//   const d = new Date(date);
//   switch (aggregation) {
//     case "day":
//       return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "short" });
//     case "week": {
//       const day = d.getDay() || 7;
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

// // Генерация ключа для группировки по периоду
// const getKey = (date, aggregation) => {
//   const d = new Date(date);
//   switch (aggregation) {
//     case "day":
//       return d.toISOString().split("T")[0];
//     case "week": {
//       const day = d.getDay() || 7;
//       const monday = new Date(d);
//       monday.setDate(d.getDate() - day + 1);
//       return monday.toISOString().split("T")[0];
//     }
//     case "month":
//       return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
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

//     if (selectedMetrics.includes("video_count")) {
//       allData = [...allData, ...publushedVideo];
//     }

//     // === Группировка по ключам (дни / недели / месяцы) ===
//     const grouped = {};
//     allData.forEach((item) => {
//       const date = item.date ?? item.date_published ?? item.date_published_from;
//       const key = getKey(date, aggregation);
//       if (!grouped[key]) grouped[key] = [];
//       grouped[key].push(item);
//     });

//     // === Сортировка по времени ===
//     const sortedKeys = Object.keys(grouped).sort(
//       (a, b) => new Date(a) - new Date(b)
//     );

//     // === Метки для оси X ===
//     const labels = sortedKeys.map((key) => formatDate(key, aggregation));

//     // === Формируем datasets (разница с предыдущим периодом) ===
//     const datasets = selectedMetrics.map((metric) => {
//       const totals = sortedKeys.map((key) => {
//         const items = grouped[key];
//         const total = items.reduce((sum, item) => {
//           if (metric === "video_count") return sum + (item.video_count ?? 0);
//           return sum + (item[metric] ?? 0);
//         }, 0);
//         return total;
//       });

//       // считаем прирост относительно предыдущего периода
//       const diffs = totals.map((value, index) => {
//         if (index === 0) return value; // можно вернуть 0, если нужен прирост от начала
//         return value - totals[index - 1];
//       });

//       return {
//         label: LABELS[metric] || metric,
//         data: diffs,
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

// === Форматирование меток оси X ===
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

// === Генерация ключа для группировки по периоду ===
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

    // === Группировка по периодам (дни / недели / месяцы) ===
    const grouped = {};
    allData.forEach((item) => {
      const date = item.date ?? item.date_published ?? item.date_published_from;
      const key = getKey(date, aggregation);
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(item);
    });

    // === Сортировка по времени ===
    const sortedKeys = Object.keys(grouped).sort(
      (a, b) => new Date(a) - new Date(b)
    );

    // === Метки для оси X ===
    const labels = sortedKeys.map((key) => formatDate(key, aggregation));

    // === Формируем datasets ===
    const datasets = selectedMetrics.map((metric) => {
      const totals = sortedKeys.map((key) => {
        const items = grouped[key];
        // Сумма значений по периоду
        return items.reduce((sum, item) => {
          if (metric === "video_count") return sum + (item.video_count ?? 0);
          return sum + (item[metric] ?? 0);
        }, 0);
      });

      // === Если это video_count, берём данные как есть ===
      const data =
        metric === "video_count"
          ? totals
          : totals.map((value, index) => {
              if (index === 0) return 0; // начало графика с нуля
              const diff = value - totals[index - 1];
              return diff < 0 ? 0 : diff; // отрицательные → 0
            });

      return {
        label: LABELS[metric] || metric,
        data,
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
