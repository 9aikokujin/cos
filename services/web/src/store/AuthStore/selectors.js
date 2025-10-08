export const authSelectors = {
  user: (state) => state.user,
  userTG: (state) => state.userTG,
  token: (state) => state.token,
  isAuthenticated: (state) => !!state.user,
  isLoading: (state) => state.isLoading,
  error: (state) => state.error,
};
