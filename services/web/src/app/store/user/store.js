import { create } from "zustand";
import { initialAuthState } from "./main";
import { createAuthActions } from "./actions";

export const useAuthStore = create((set, get) => ({
  ...initialAuthState,
  ...createAuthActions(set, get),
}));
