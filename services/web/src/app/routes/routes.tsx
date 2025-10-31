import React from "react";
import { lazy } from "react";
import { redirect } from "react-router-dom";
import { useAuthStore } from "../store/user/store";

import AppUsermodal from "@/components/typeModal/addUser/AddUserModal";

// Импорт страниц
const AuthPage = lazy(() => import("@/pages/authPage/AuthPage"));
const ProxyPage = lazy(() => import("@/pages/proxyPage/ProxyPage"));
const UserPage = lazy(() => import("@/pages/userPage/UserPage"));
const EditProfilePage = lazy(() => import("@/pages/editProfilePage/EditProfilePage"));
const AccountsPage = lazy(() => import("@/pages/accountsPage/AccountsPage"));
const VideosPage = lazy(() => import("@/pages/videosPage/VideosPage"));
const StatisticPage = lazy(() => import("@/pages/statisticPage/StatisticPage"));
const NotFoundPage = lazy(() => import("@/pages/notFoundPage/NotFoundPage"));

export enum AppRoutes {
  AUTH = "/auth",
  EDITPROFILE = "/edit-profile/:id",
  PROXY = "/proxy",
  USER = "/user",
  ACCOUNTS = "/accounts",
  VIDEOS = "/videos",
  VIDEOS_USER = "/videos/:id",
  STATISTIC = "/statistic",
  STATISTIC_USER = "/statistic/:id",
  NOT_FOUND = "*",
}

export const authLoader = () => {
  const { isAuthenticated } = useAuthStore.getState();

  if (isAuthenticated) {
    const defaultRoute = "/";

    return redirect(defaultRoute);
  }

  return null;
};

// Базовые маршруты
const baseRoutes = [
  { path: AppRoutes.AUTH, element: <AuthPage />, loader: authLoader },
  { path: AppRoutes.NOT_FOUND, element: <NotFoundPage /> },
];

// Админские маршруты
const adminRoutes = [
  {
    path: AppRoutes.USER,
    element: <UserPage />,
    handle: {
      header: {
        showAddButton: true,
        showProxySettings: true,
        showAccount: true,
        modal: {
          height: "40vh",
          content: <AppUsermodal />,
        },
      },
    },
  },
  { path: AppRoutes.EDITPROFILE, element: <EditProfilePage /> },
  {
    path: AppRoutes.PROXY,
    element: <ProxyPage />,
  },
  {
    path: AppRoutes.ACCOUNTS,
    element: <AccountsPage />,
    handle: {
      header: {
        showAddButton: false,
        showProxySettings: true,
        showAccount: true,
        modal: {
          title: "Добавить канал",
          content: <div> добавить канал </div>,
        },
      },
    },
  },
  {
    path: AppRoutes.VIDEOS,
    element: <VideosPage />,
    handle: {
      header: {
        showAddButton: false,
        showProxySettings: true,
        showAccount: true,
        modal: {
          title: "Добавить видео",
          content: <div> добавить видео </div>,
        },
      },
    },
  },
  { path: AppRoutes.STATISTIC, element: <StatisticPage /> },
];

// Пользовательские маршруты
const userRoutes = [
  {
    path: AppRoutes.VIDEOS_USER,
    element: <VideosPage />,
    handle: {
      header: {
        showAddButton: false,
        showProxySettings: false,
        showAccount: true,
        modal: {
          title: "Добавить видео",
          content: <div> добавить видео </div>,
        },
      },
    },
  },
  { path: AppRoutes.EDITPROFILE, element: <EditProfilePage /> },
  { path: AppRoutes.STATISTIC_USER, element: <StatisticPage /> },
];

// Генерация маршрутов по роли
export const getRoutesByRole = (role: "admin" | "user", userId?: string, isAuth: boolean) => {
  if (!isAuth) {
    return [...baseRoutes, ...userRoutes, ...adminRoutes];
  }

  if (role === "admin") {
    return [...baseRoutes, ...adminRoutes];
  }

  // const userSpecificRoutes = userRoutes.map((route) => ({
  //   ...route,
  //   path: route.path?.replace(":id", userId || ""),
  // }));

  return [...baseRoutes, ...userRoutes];
};
