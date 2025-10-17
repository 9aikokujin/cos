import { create } from "zustand";
import { createFilterActions } from "./actions";
import { initialFilterState } from "./main";

export const useFilterStore = create((set, get) => ({
  ...initialFilterState,
  ...createFilterActions(set, get),
}));
