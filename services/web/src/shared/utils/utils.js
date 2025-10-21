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
  return fields.reduce((result, field) => {
    result[field] = array.reduce((sum, item) => sum + (item[field] || 0), 0);
    return result;
  }, {});
}
