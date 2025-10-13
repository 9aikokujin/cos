import { create } from "zustand";
import { initialNotificationState } from "./main";
import { createNotificationActions } from "./actions";

export const useNotificationStore = create((set, get) => ({
  ...initialNotificationState,
  ...createNotificationActions(set, get),
}));
