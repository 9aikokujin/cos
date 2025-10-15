import { Suspense, useMemo } from "react";
import { RouterProvider, createBrowserRouter } from "react-router-dom";

import { useAppRouterConfig } from "./app/routes/AppRouter";

import Layout from "./app/layout/Layout";
import Loader from "./components/loader/Loader";
import { useAuthStore } from "./app/store/user/store";

function App() {
  const routeConfig = useAppRouterConfig();
  const { isLoading } = useAuthStore();

  const router = useMemo(() => {
    return createBrowserRouter([
      {
        element: <Layout />,
        children: routeConfig,
      },
    ]);
  }, [routeConfig]);

  if (isLoading) return <Loader />;
  
  return (
    <Suspense fallback={<Loader />}>
      <RouterProvider router={router} />
    </Suspense>
  );
}

export default App;
