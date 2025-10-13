import { initialFilterModalState } from "./main";

export const createFilterModalActions = (set, get) => ({
  open: (filters, onApply) => set({ isOpen: true, filters, onApply, stack: [] }),

  close: () => set(initialFilterModalState),

  push: (filter) => set((state) => ({ stack: [...state.stack, filter] })),
  pop: () =>
    set((state) => {
      if (state.stack.length > 0) {
        return { stack: state.stack.slice(0, -1) };
      }
      return state;
    }),

  setFooter: (footer) => set((state) => ({ footer: { ...state.footer, ...footer } })),
});
