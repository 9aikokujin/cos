import API from "@/app/api";

export const createAuthActions = (set, get) => ({
  register: async (data) => {
    set({ isLoading: true });
    try {
      const response = await API.auth.register(data);
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
    // set({
    //   isAuthenticated: true,
    //   user: {
    //     id: "123",
    //     role: "admin",
    //     fullname: "string",
    //     first_name: "string",
    //     last_name: "string",
    //   },
    // });

    set({ isLoading: true });
    try {
      const response = await API.auth.authTG();
      if (response.status) {
        set({ user: response, userTG: user, isAuthenticated: response.status });
      } else {
        set({ userTG: user });
      }
    } finally {
      set({ isLoading: false });
    }
  },
  setToken: (token) => {
    set({ token });
  },
});
