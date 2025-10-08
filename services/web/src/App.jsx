import { useEffect } from "react";
import { BrowserRouter, useLocation } from "react-router-dom";
import { initData } from "@telegram-apps/sdk-react";

import AppRouter from "@/routing/AppRouter";
import Header from "@/components/header/Header";
import { useAuth } from "@/store/AuthStore/main";
import Footer from "@/components/footer/Footer";
import { LoaderProvider } from "@/ui/loader/LoaderContext";

function App() {
  const {
    isAuthenticated,
    actions: { authTG, setToken },
  } = useAuth();



  useEffect(() => {
    authTG(initData.raw(), initData.user());
    setToken(initData.raw());
  }, []);

  return (
    <>
      <BrowserRouter>
        {/* <LoaderProvider> */}
        <div className="layout">
          <Header />
          <main className="main__content">
            <AppRouter />
          </main>
          {isAuthenticated && <Footer />}
        </div>
        {/* </LoaderProvider> */}
      </BrowserRouter>
    </>
  );
}

export default App;
