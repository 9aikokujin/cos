import { useState, useEffect, useRef, useCallback } from "react";

export const useScrollWithSearch = ({
  fetchFn,
  initialPage = 1,
  pageSize = 10,
  searchTerm = "",
  additionalParams = {},
}) => {
  const [items, setItems] = useState([]);
  const [page, setPage] = useState(initialPage);
  const [hasMore, setHasMore] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const observerRef = useRef(null);
  const lastItemRef = useRef(null);

  const fetchItems = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const result = await fetchFn({
        page,
        size: pageSize,
        search: searchTerm,
        ...additionalParams,
      });

      setItems((prev) => (page === initialPage ? result.items : [...prev, ...result.items]));
      setHasMore(result.items.length === pageSize);
    } catch (err) {
      setError(err);
    } finally {
      setIsLoading(false);
    }
  }, [fetchFn, searchTerm, additionalParams]);

  const updateItem = useCallback((id, update) => {
    setItems((prev) => {
      if (update === null) {
        return prev.filter((item) => item?.id !== id);
      } else if (typeof update === "function") {
        return prev.map((item) => (item?.id === id ? update(item) : item));
      } else {
        return prev.map((item) => (item?.id === id ? { ...item, ...update } : item));
      }
    });
  }, []);

  useEffect(() => {
    setPage(initialPage);
    setItems([]);
    setHasMore(true);
  }, [searchTerm, initialPage]);

  useEffect(() => {
    fetchItems();
  }, [searchTerm, page]);

  const setLastItemRef = useCallback(
    (node) => {
      if (isLoading) return;
      if (observerRef.current) observerRef.current.disconnect();

      observerRef.current = new IntersectionObserver(
        (entries) => {
          if (entries[0].isIntersecting && hasMore && !isLoading) {
            setPage((prev) => prev + 1);
          }
        },
        { threshold: 1.0 }
      );

      if (node) {
        lastItemRef.current = node;
        observerRef.current.observe(node);
      }
    },
    [isLoading, hasMore]
  );

  useEffect(() => {
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, []);

  return {
    items,
    isLoading,
    error,
    hasMore,
    updateItem,
    setLastItemRef,
    reset: () => {
      setPage(initialPage);
      setItems([]);
      setHasMore(true);
    },
    refetch: () => {
      fetchItems();
    },
  };
};
