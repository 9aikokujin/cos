export const createEntityActions = (set, get) => ({
  setTerm: (term) => set({ term }),
  setItems: (items) => set({ items }),
  appendItems: (newItems) => set((state) => ({ items: [...state.items, ...newItems] })),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  setHasMore: (hasMore) => set({ hasMore }),
  reset: () => set({ items: [], page: 1, hasMore: true, error: null }),
  nextPage: () => set((state) => ({ page: state.page + 1 })),
});
