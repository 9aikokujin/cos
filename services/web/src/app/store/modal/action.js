export const createModalActions = (set, get) => ({
  openModal: (content, options = {}) =>
    set({
      modal: { content, height: options.height || "auto" },
      isOpen: true,
    }),
  closeModal: () => set({ isOpen: false, modal: null }),
});
