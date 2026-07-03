import { createContext, useContext } from "react";

export type ViewMode = "desktop" | "mobile";

export const ViewModeCtx = createContext<{ mode: ViewMode; toggle: () => void }>({
  mode: "mobile",
  toggle: () => {},
});

export const useViewMode = () => useContext(ViewModeCtx);
