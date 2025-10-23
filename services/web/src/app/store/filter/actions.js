export const createFilterActions = (set, get) => ({
  setFilter: (filter) => set({ filter: { ...get().filter, ...filter } }),

  setFilterTag: (tag) => set({ tag }),

  setFilterId: (id) => set({ filter: { ...get().filter, id } }),

  setFilterUserId: (user_id) => set({ filter: { ...get().filter, user_id } }),

  setFilterDatePublishedTo: (date_published_to) =>
    set({ filter: { ...get().filter, date_published_to } }),

  setFilterDatePublishedFrom: (date_published_from) =>
    set({ filter: { ...get().filter, date_published_from } }),

  setFilterChannelType: (channel_type) => set({ filter: { ...get().filter, channel_type } }),

  setFilterChannelId: (channel_id) => set({ filter: { ...get().filter, channel_id } }),

  setFilterVideoId: (video_id) => set({ filter: { ...get().filter, video_id } }),

  setFilterDateFrom: (date_from) => set({ filter: { ...get().filter, date_from } }),

  setFilterDateTo: (date_to) => set({ filter: { ...get().filter, date_to } }),

  setWithTags: (withTags) => set({ withTags }),
  setIsLoading: (isLoading) => set({ isLoading }),

  resetFilter: () =>
    set({
      filter: {
        articles: "",
        id: "",
        user_id: "",
        date_published_to: "",
        date_published_from: "",
        channel_type: "",
        channel_id: "",
        video_id: "",
        date_from: "",
        date_to: "",
      },
    }),
});
