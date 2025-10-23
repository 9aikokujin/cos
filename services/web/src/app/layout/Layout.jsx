import { Outlet, useLocation } from "react-router-dom";

import { AppRoutes } from "@/app/routes/routes";

import Header from "./header/Header";
import Footer from "./footer/Footer";
import AppModals from "@/components/typeModal/AppModal";

const Layout = () => {
  const location = useLocation();
  console.log(location.pathname);
  const hideFooter = location.pathname === AppRoutes.AUTH;
  return (
    <div className="app">
      <Header />
      <main className="main">
        <Outlet />
        <AppModals />
      </main>
      {!hideFooter && <Footer />}
    </div>
  );
};

export default Layout;
