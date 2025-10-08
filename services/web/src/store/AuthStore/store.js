import { create } from "zustand";
import { authActions } from "./actions";

export const initialAuthState = {
  user: null,
  userTG: null,
  token: "",
  isLoading: false,
  error: null,
  isAuthenticated: false,
};

export const createAuthStore = () =>
  create((set, get) => ({
    ...initialAuthState,
    actions: authActions(set, get),
  }));
