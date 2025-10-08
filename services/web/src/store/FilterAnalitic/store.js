import { create } from "zustand";

import { filterActions } from "./actions";

export const initialFilterState = {
  filter: {
    group_by: null,
    hashtag: null,
    channel_id: null,
    channel_type: null,
    date_from: null,
    date_to: null,
    video_url: null,
  },
};

export const createFilterStore = () =>
  create((set, get) => ({
    ...initialFilterState,
    actions: filterActions(set, get),
  }));
