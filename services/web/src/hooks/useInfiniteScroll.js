import { useEffect, useRef, useCallback } from "react";

export const useInfiniteScroll = (store, fetchFn, entity, deps = []) => {
  const {
    items,
    page,
    hasMore,
    isLoading,
    setItems,
    appendItems,
    setLoading,
    setError,
    setHasMore,
    nextPage,
    reset,
  } = store();

  const observerRef = useRef(null);

  const fetchItems = useCallback(async () => {
    if (isLoading || !hasMore) return;
    setLoading(true);
    setError(null);

    try {
      const result = await fetchFn(page);
      const data = result?.[entity] || result;

      if (page === 1) setItems(data);
      else appendItems(data);

      setHasMore(data.length > 0);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [page, ...deps]);

  useEffect(() => {
    fetchItems();
  }, [page, ...deps]);

  const lastItemRef = useCallback(
    (node) => {
      if (isLoading) return;
      if (observerRef.current) observerRef.current.disconnect();

      observerRef.current = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && hasMore && !isLoading) {
          nextPage();
        }
      });

      if (node) observerRef.current.observe(node);
    },
    [isLoading, hasMore]
  );

  useEffect(() => {
    return () => observerRef.current?.disconnect();
  }, []);

  return { items, isLoading, hasMore, lastItemRef, reset };
};
