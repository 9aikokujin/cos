export const createNotificationActions = (set, get) => ({
  showNotification: (message, type = "error") => set({ notification: { message, type } }),
  clearNotification: () => set({ notification: null }),

  showNotification: (content) => set({ notification: content, isOpen: true }),
  closeNotification: () => set({ isOpen: false, notification: null }),
});
