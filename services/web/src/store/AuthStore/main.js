import { authSelectors } from "./selectors";
import { createAuthStore } from "./store";

export const authStore = createAuthStore();

export const useAuth = () => {
  const state = authStore();
  return {
    ...state,
    actions: state.actions,
    selectors: authSelectors,
  };
};

export const useAuthUser = () => useAuth(authSelectors.user);
export const useUserTG = () => useAuth(authSelectors.userTG);
export const useToken = () => useAuth(authSelectors.token);
export const useIsAuthenticated = () => useAuth(authSelectors.isAuthenticated);
export const useAuthLoading = () => useAuth(authSelectors.isLoading);
export const useAuthError = () => useAuth(authSelectors.error);
