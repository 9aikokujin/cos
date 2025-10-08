import { createContext, useContext, useState } from "react";
import GlobalLoader from "./Loader";

const LoaderContext = createContext();

export const LoaderProvider = ({ children }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  const showLoader = () => {
    setIsLoading(true);
    setIsVisible(true);
  };

  const hideLoader = () => {
    setIsVisible(false);
    setTimeout(() => setIsLoading(false), 300);
  };

  return (
    <LoaderContext.Provider value={{ showLoader, hideLoader }}>
      {children}
      {isLoading && <GlobalLoader isVisible={isVisible} />}
    </LoaderContext.Provider>
  );
};

export const useLoader = () => useContext(LoaderContext);
