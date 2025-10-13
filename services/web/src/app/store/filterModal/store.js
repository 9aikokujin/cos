import { create } from "zustand";

import { createFilterModalActions } from "./actions";
import { initialFilterModalState } from "./main";

export const useFiltersModalStore = create((set, get) => ({
  ...createFilterModalActions(set, get),
  ...initialFilterModalState,
}));
