import { createContext, useContext } from "react";

export type ViewId =
  | "today"
  | "board"
  | "upcoming"
  | "meetings"
  | "book"
  | "week"
  | "sprint"
  | "backlog"
  | "projects"
  | "notes"
  | "goals"
  | "skills"
  | "reviews"
  | "knowledge"
  | "career"
  | "ai"
  | "analytics"
  | "settings";

/** App-wide UI actions, provided once by the shell. */
export interface UiActions {
  navigate: (view: ViewId, arg?: string) => void;
  openTask: (id: string) => void;
  openCapture: (initial?: string) => void;
  openPalette: () => void;
  openShortcuts: () => void;
  openLogCall: (draft?: { start?: string; minutes?: number }) => void;
}

export const UiContext = createContext<UiActions | null>(null);

export function useUi(): UiActions {
  const ctx = useContext(UiContext);
  if (!ctx) throw new Error("useUi outside provider");
  return ctx;
}
