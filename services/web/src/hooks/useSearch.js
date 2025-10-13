import { useState, useEffect } from "react";

import { debounce } from "@/shared/utils/debounce";

export const useSearch = (store, fetchFn, entity, delay = 400) => {
  const [searchTerm, setSearchTerm] = useState("");
  const { reset, setItems, setLoading, setError, setHasMore } = store();

  const performSearch = debounce(async (term) => {
    if (!term.trim()) {
      reset();
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await fetchFn(term);
      const data = result?.[entity] || result;
      setItems(data);
      setHasMore(false);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, delay);

  useEffect(() => {
    performSearch(searchTerm);
    return () => performSearch.cancel();
  }, [searchTerm]);

  return {
    searchTerm,
    setSearchTerm,
  };
};
