import { Suspense } from "react";

import ProtectedRoute from "./ProtectedRoute";
import AuthRedirect from "./AuthRedirect";

import AdminPage from "@/components/adminPage/AdminPage";
import Registration from "@/components/registration/Registration";
import DiagramPage from "@/page/diagramPage/DiagramPage";
import EditProfilePage from "@/page/editProfilePage/EditProfilePage";
import AccountListPage from "@/page/accountListPage/AccountListPage";
import VideoListPage from "@/page/videoListPage/VideoListPage";
import BlockPage from "@/page/blockPage/BlockPage";
import GlobalLoader from "@/ui/loader/Loader";

export const routesConfig = () => [
  {
    path: "/auth/register",
    element: (
      <AuthRedirect>
        <Suspense fallback={<GlobalLoader />}>
          <Registration />
        </Suspense>
      </AuthRedirect>
    ),
  },
  {
    path: "/",
    element: (
      <ProtectedRoute allowedRoles={["admin"]}>
        <Suspense fallback={<GlobalLoader />}>
          <AdminPage />
        </Suspense>
      </ProtectedRoute>
    ),
  },
  {
    path: "/diagram",
    element: (
      // <ProtectedRoute allowedRoles={["admin"]}>
      <Suspense fallback={<GlobalLoader />}>
        <DiagramPage />
      </Suspense>
      // </ProtectedRoute>
    ),
  },
  {
    path: "/diagram/:id",
    element: (
      // <ProtectedRoute allowedRoles={["admin", "user"]}>
      <Suspense fallback={<GlobalLoader />}>
        <DiagramPage />
      </Suspense>
      // </ProtectedRoute>
    ),
  },
  {
    path: "/edit",
    element: (
      <ProtectedRoute allowedRoles={["admin", "user"]}>
        <Suspense fallback={<GlobalLoader />}>
          <EditProfilePage />
        </Suspense>
      </ProtectedRoute>
    ),
  },
  {
    path: "/edit/:id",
    element: (
      <ProtectedRoute allowedRoles={["admin"]}>
        <Suspense fallback={<GlobalLoader />}>
          <EditProfilePage />
        </Suspense>
      </ProtectedRoute>
    ),
  },
  {
    path: "/account-list",
    element: (
      <ProtectedRoute allowedRoles={["admin"]}>
        <Suspense fallback={<GlobalLoader />}>
          <AccountListPage />
        </Suspense>
      </ProtectedRoute>
    ),
  },
  {
    path: "/video-list",
    element: (
      <ProtectedRoute allowedRoles={["admin", "user"]}>
        <Suspense fallback={<GlobalLoader />}>
          <VideoListPage />
        </Suspense>
      </ProtectedRoute>
    ),
  },
  {
    path: "/block",
    element: (
      <ProtectedRoute allowedRoles={["admin", "user"]}>
        <Suspense fallback={<GlobalLoader />}>
          <BlockPage />
        </Suspense>
      </ProtectedRoute>
    ),
  },
];
