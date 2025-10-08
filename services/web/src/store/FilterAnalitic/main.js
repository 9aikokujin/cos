import { createFilterStore } from "./store";

export const filterStore = createFilterStore();

export const useFilter = () => {
  const state = filterStore();
  return {
    ...state,
    actions: state.actions,
  };
};
