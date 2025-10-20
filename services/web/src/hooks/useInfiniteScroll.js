import { useEffect, useRef, useCallback } from "react";
import { useFilterStore } from "@/app/store/filter/store";

export const useInfiniteScroll = (store, fetchFn, entity, deps = []) => {
  const {
    items,
    page,
    term,
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

  const filter = useFilterStore((state) => state.filter);

  const observerRef = useRef(null);

  const fetchItems = useCallback(async () => {
    if (isLoading || !hasMore) return;

    setLoading(true);
    setError(null);

    try {
      const result = await fetchFn(page, term, filter);

      const data = (entity ? result?.[entity] : result) ?? [];

      if (page === 1) setItems(data);
      else appendItems(data);

      setHasMore(data.length >= 10);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [page, term, filter, hasMore]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems, term, filter]);

  useEffect(() => {
    reset();
  }, [term, filter, ...deps]);

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
