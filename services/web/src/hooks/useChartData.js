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

// ===== Утилиты =====
const pad = (n) => String(n).padStart(2, "0");

/**
 * Надёжный локальный парсер ISO-like строк.
 * Поддерживает форматы:
 *  - "2021-04-17T00:00:00"
 *  - "2021-04-17 00:00:00"
 *  - "2021-04-17"
 * Если передан уже Date — возвращает копию.
 */
const parseLocalDate = (value) => {
  if (!value) return new Date(NaN);

  if (value instanceof Date) return new Date(value.getTime());

  if (typeof value !== "string") return new Date(value);

  // Попробуем распарсить числа: YYYY-MM-DD[ T hh:mm:ss]
  const isoRe = /^(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{2}):(\d{2})(?::(\d{2}))?)?/;
  const m = value.match(isoRe);
  if (m) {
    const year = parseInt(m[1], 10);
    const month = parseInt(m[2], 10) - 1; // monthIndex
    const day = parseInt(m[3], 10);
    const hour = m[4] ? parseInt(m[4], 10) : 0;
    const minute = m[5] ? parseInt(m[5], 10) : 0;
    const second = m[6] ? parseInt(m[6], 10) : 0;
    // new Date(...) — создаёт локальную дату (не UTC)
    return new Date(year, month, day, hour, minute, second);
  }

  // fallback: попробуем стандартный конструктор
  return new Date(value);
};

/** Возвращает ключ YYYY-MM-DD по локальной дате (без использования toISOString) */
const localDateKey = (d) => {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

/** Нахождение понедельника той же недели (локально) */
const getMondayLocal = (d) => {
  const copy = new Date(d.getTime());
  const day = copy.getDay() || 7; // воскресенье -> 7
  copy.setDate(copy.getDate() - day + 1);
  return copy;
};

// === Форматирование меток оси X ===
const formatDate = (date, aggregation) => {
  const d = parseLocalDate(date);
  switch (aggregation) {
    case "day":
      return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "short" });
    case "week": {
      const monday = getMondayLocal(d);
      return monday.toLocaleDateString("ru-RU", { day: "2-digit", month: "short" });
    }
    case "month":
      return d.toLocaleString("ru-RU", { month: "short", year: "numeric" });
    default:
      return d.toLocaleDateString();
  }
};

// === Генерация ключа для группировки по периоду (локально) ===
const getKey = (date, aggregation) => {
  const d = parseLocalDate(date);
  switch (aggregation) {
    case "day":
      return localDateKey(d);
    case "week": {
      const monday = getMondayLocal(d);
      return localDateKey(monday);
    }
    case "month":
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}`; // YYYY-MM
    default:
      return localDateKey(d);
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

    // === Группировка по локальным ключам ===
    const grouped = {};
    allData.forEach((item) => {
      const dateStr = item.date ?? item.date_published ?? item.date_published_from;
      const key = getKey(dateStr, aggregation);
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(item);
    });

    // === Сортировка ключей по локальной дате ===
    const sortedKeys = Object.keys(grouped).sort((a, b) => {
      // для month вида "YYYY-MM" — безопасно распарсить как Date
      const pa = a.length === 7 ? `${a}-01` : a;
      const pb = b.length === 7 ? `${b}-01` : b;
      const daParts = pa.split("-").map(Number);
      const dbParts = pb.split("-").map(Number);
      // создаём локальные даты для сравнения
      const da = new Date(daParts[0], (daParts[1] || 1) - 1, daParts[2] || 1);
      const db = new Date(dbParts[0], (dbParts[1] || 1) - 1, dbParts[2] || 1);
      return da - db;
    });

    // Метки для оси X — используем ключ как исходник для formatDate
    const labels = sortedKeys.map((key) => {
      // для month ключа "YYYY-MM" превращаем в "YYYY-MM-01"
      const dateForFormat = key.length === 7 ? `${key}-01` : key;
      return formatDate(dateForFormat, aggregation);
    });

    // Формируем datasets
    const datasets = selectedMetrics.map((metric) => {
      const totals = sortedKeys.map((key) => {
        const items = grouped[key];
        return items.reduce((sum, item) => {
          if (metric === "video_count") return sum + (item.video_count ?? 0);
          return sum + (item[metric] ?? 0);
        }, 0);
      });

      const data =
        metric === "video_count"
          ? totals
          : totals.map((value, index) => {
              if (index === 0) return 0; // начало графика с нуля
              const diff = value - totals[index - 1];
              return diff < 0 ? 0 : diff;
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
