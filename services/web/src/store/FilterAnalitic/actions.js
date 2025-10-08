import dayjs from "dayjs";
import { initialFilterState } from "./store";

export const filterActions = (set) => ({
  setRangeFilter: (range) => {
    set((state) => ({
      filter: {
        ...state.filter,
        ...(range.start && { date_from: dayjs(range.start).format("YYYY-MM-DD") }),
        ...(range.end && { date_to: dayjs(range.end).format("YYYY-MM-DD") }),
      },
    }));
  },
  setChannelType: (type) => {
    set((state) => ({
      filter: {
        ...state.filter,
        channel_type: type,
      },
    }));
  },
  setChannelID: (channel_id) => {
    set((state) => ({
      filter: {
        ...state.filter,
        channel_id: channel_id,
      },
    }));
  },
  setVideoUrl: (videoUrl) => {
    set((state) => ({
      filter: {
        ...state.filter,
        video_url: videoUrl,
      },
    }));
  },
  setHashtag: (hashtag) => {
    set((state) => ({
      filter: {
        ...state.filter,
        hashtag: hashtag,
      },
    }));
  },
  resetFilter: () => {
    set({ filter: initialFilterState.filter });
  },
});
