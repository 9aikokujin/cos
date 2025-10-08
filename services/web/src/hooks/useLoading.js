import { useState } from "react";

export const useLoading = () => {
  const [isLoading, setIsLoading] = useState(false);

  const withLoading = async (callback) => {
    setIsLoading(true);
    try {
      const result = await callback();
      return result;
    } finally {
      setIsLoading(false);
    }
  };

  return { isLoading, withLoading };
};

export const useApi = () => {
  const { isLoading, withLoading } = useLoading();

  const callApi = async (apiFunction, ...args) => {
    return withLoading(() => apiFunction(...args));
  };

  return { isLoading, callApi };
};
