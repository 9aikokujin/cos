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


