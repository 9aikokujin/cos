import API from "@/app/api";

export const createAuthActions = (set, get) => ({
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
    set({
      isAuthenticated: true,
      user: {
        id: "123",
        role: "admin",
        fullname: "string",
        first_name: "string",
        last_name: "string",
      },
    });

    // set({ isLoading: true });
    // try {
    //   const response = await API.auth.authTG(data);
    //   if (response.status) {
    //     set({ user: response, userTG: user, isAuthenticated: true });
    //   } else {
    //     set({ userTG: user });
    //   }
    // } finally {
    //   set({ isLoading: false });
    // }
  },
  setToken: (token) => {
    set({ token });
  },
});
