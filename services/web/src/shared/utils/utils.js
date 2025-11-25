import { AppRoutes } from "@/app/routes/routes";

export const socialNetworks = ["Instagram", "YouTube", "Likee", "TikTok"];

export const footerBaseLinks = [
  { path: AppRoutes.VIDEOS_USER, icon: "video", matchSubpaths: true },
  { path: AppRoutes.STATISTIC_USER, icon: "statistic", matchSubpaths: true },
];

export const footerAdminLinks = [
  { path: AppRoutes.USER, icon: "customer" },
  { path: AppRoutes.ACCOUNTS, icon: "accounts" },
  { path: AppRoutes.VIDEOS, icon: "video" },
  { path: AppRoutes.STATISTIC, icon: "statistic", matchSubpaths: true },
];

export function sumFields(array, fields) {
  // if (!array?.length) {
  //   return Object.fromEntries(fields.map((f) => [f, 0]));
  // }

  // // Находим элемент с самой поздней датой
  // const latestItem = array.reduce((latest, item) => {
  //   const itemDate = new Date(item.date ?? item.date_published ?? item.date_published_from);
  //   const latestDate = new Date(latest.date ?? latest.date_published ?? latest.date_published_from);
  //   return itemDate > latestDate ? item : latest;
  // });

  // // Берём значения только из последней записи
  // return fields.reduce((result, field) => {
  //   result[field] = latestItem[field] ?? 0;
  //   return result;
  // }, {});

  if (!array?.length || !fields?.length) {
    return Object.fromEntries(fields.map((f) => [f, 0]));
  }

  const getDate = (item) =>
    new Date(
      item.date ??
      item.date_published ??
      item.date_published_from ??
      0
    );

  // 1. Сортируем по дате по возрастанию
  const sorted = [...array].sort((a, b) => getDate(a) - getDate(b));

  // 2. Инициализируем результат нулями
  const totals = Object.fromEntries(fields.map((f) => [f, 0]));

  // 3. Для каждого поля считаем приросты между соседними элементами
  for (let i = 1; i < sorted.length; i++) {
    const prev = sorted[i - 1];
    const curr = sorted[i];

    for (const field of fields) {
      const prevVal = Number(prev[field] ?? 0);
      const currVal = Number(curr[field] ?? 0);
      const diff = currVal - prevVal;

      // если diff < 0, считаем прирост 0
      const increment = diff > 0 ? diff : 0;

      totals[field] += increment;
    }
  }

  return totals;
}

export const sumVideoCounts = (array, fields) => {
  return fields.reduce((result, field) => {
    result[field] = array.reduce((sum, item) => sum + (item[field] || 0), 0);
    return result;
  }, {});
};

export const getLatestVideos = (videos) => {
  const latestByVideo = {};

  for (const video of videos) {
    const existing = latestByVideo[video.video_id];

    if (!existing) {
      latestByVideo[video.video_id] = video;
    } else {
      const existingDate = new Date(existing.updated_at);
      const newDate = new Date(video.updated_at);

      if (newDate > existingDate) {
        latestByVideo[video.video_id] = video;
      }
    }
  }

  return Object.values(latestByVideo);
};
