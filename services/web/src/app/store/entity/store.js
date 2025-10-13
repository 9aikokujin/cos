import { create } from "zustand";
import { createEntityActions } from "./actions";
import { initialEntityStore } from "./main";

const createEntityStore = () => {
  return create((set, get) => ({
    ...initialEntityStore,
    ...createEntityActions(set, get),
  }));
};

export const useUsersStore = createEntityStore();
export const useAccountStore = createEntityStore();
export const useVideosStore = createEntityStore();
