import API from "@/api";

export const authActions = (set) => ({
  register: async (data, token) => {
    set({ isLoading: true });
    try {
      const response = await API.auth.register(data, token);
      set({ user: response, isAuthenticated: true });
      return { success: true, user: response };
    } catch (err) {
      set({ error: err.message });
      return { success: false };
    } finally {
      set({ isLoading: false });
    }
  },
  authTG: async (data, user) => {
    set({ isLoading: true });
    try {
      const response = await API.auth.authTG(data);
      if (response.status) {
        set({ user: response, userTG: user, isAuthenticated: true });
      } else {
        set({ userTG: user });
      }
    } catch (err) {
      set({ error: err.message });
    } finally {
      set({ isLoading: false });
    }
  },
  setToken: (token) => set({ token: token }),
  clearError: () => set({ error: null }),
});
