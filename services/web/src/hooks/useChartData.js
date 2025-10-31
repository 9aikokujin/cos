import { useMemo } from "react";
import { COLORS, LABELS } from "@/shared/utils/chartsSettings";

const pad = (n) => String(n).padStart(2, "0");
const parseLocalDate = (value) => {
  if (!value) return new Date(NaN);
  if (value instanceof Date) return new Date(value.getTime());
  if (typeof value !== "string") return new Date(value);
  const isoRe = /^(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{2}):(\d{2})(?::(\d{2}))?)?/;
  const m = value.match(isoRe);
  if (m) {
    const year = parseInt(m[1], 10);
    const month = parseInt(m[2], 10) - 1;
    const day = parseInt(m[3], 10);
    const hour = m[4] ? parseInt(m[4], 10) : 0;
    const minute = m[5] ? parseInt(m[5], 10) : 0;
    const second = m[6] ? parseInt(m[6], 10) : 0;
    return new Date(year, month, day, hour, minute, second);
  }
  return new Date(value);
};
const localDateKey = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const getMondayLocal = (d) => {
  const copy = new Date(d.getTime());
  const day = copy.getDay() || 7;
  copy.setDate(copy.getDate() - day + 1);
  return copy;
};
const getKey = (date, aggregation) => {
  const d = parseLocalDate(date);
  switch (aggregation) {
    case "day": return localDateKey(d);
    case "week": return localDateKey(getMondayLocal(d));
    case "month": return `${d.getFullYear()}-${pad(d.getMonth() + 1)}`;
    default: return localDateKey(d);
  }
};
const formatDate = (date, aggregation) => {
  const d = parseLocalDate(date);
  switch (aggregation) {
    case "day": return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "short" });
    case "week": return getMondayLocal(d).toLocaleDateString("ru-RU", { day: "2-digit", month: "short" });
    case "month": return d.toLocaleString("ru-RU", { month: "short", year: "numeric" });
    default: return d.toLocaleDateString();
  }
};

export const useChartData = (
  statistic = [],
  publishedVideo = [],
  selectedMetrics = [],
  aggregation = "day",
  userFromDate // может быть undefined
) => {
  console.log(statistic)
  return useMemo(() => {
    let allData = [...statistic];
    if (selectedMetrics.includes("video_count")) {
      allData = [...allData, ...publishedVideo];
    }

    // группировка
    const grouped = {};
    allData.forEach(item => {
      const dateStr = item.date ?? item.date_published ?? item.date_published_from;
      const key = getKey(dateStr, aggregation);
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(item);
    });

    // сортировка
    const sortedKeys = Object.keys(grouped).sort((a, b) => parseLocalDate(a.length === 7 ? `${a}-01` : a) - parseLocalDate(b.length === 7 ? `${b}-01` : b));

    // определяем видимые ключи
    let startIndex = 0;
    if (userFromDate) {
      const idx = sortedKeys.findIndex(k => k >= userFromDate);
      startIndex = idx >= 0 ? idx : 0;
    }
    const visibleKeys = sortedKeys.slice(startIndex);

    // метки
    const labels = visibleKeys.map(k => {
      const date = k.length === 7 ? `${k}-01` : k;
      return formatDate(date, aggregation);
    });

    // datasets
    const datasets = selectedMetrics.map(metric => {
      const totals = sortedKeys.map(k => {
        const items = grouped[k];
        return items.reduce((sum, item) => metric === "video_count" ? sum + (item.video_count ?? 0) : sum + (item[metric] ?? 0), 0);
      });

      const data = visibleKeys.map((k, idx) => {
        const fullIndex = startIndex + idx;
        if (metric === "video_count") return totals[fullIndex];

        // прирост
        const prevTotal = fullIndex > 0 ? totals[fullIndex - 1] : 0;
        return fullIndex === 0 ? 0 : Math.max(totals[fullIndex] - prevTotal, 0);
      });

      return {
        label: LABELS[metric] || metric,
        data,
        originalTotals: visibleKeys.map((_, idx) => totals[startIndex + idx]),
        borderColor: COLORS[metric],
        borderWidth: 1.5,
        tension: 0.3,
        pointBackgroundColor: "#fff",
        pointBorderColor: COLORS[metric],
        pointRadius: 3,
      };
    });

    return { labels, datasets };
  }, [statistic, publishedVideo, selectedMetrics, aggregation, userFromDate]);
};
