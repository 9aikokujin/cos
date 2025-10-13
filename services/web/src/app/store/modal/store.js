import { create } from "zustand";
import { createModalActions } from "./action";
import { initialModalState } from "./main";

export const useModalStore = create((set, get) => ({
  ...initialModalState,
  ...createModalActions(set, get),
}));
