import { createContext, useContext } from "react";
import type { MeetingSeries } from "./types";

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
  | "workflows"
  | "boards"
  | "people"
  | "analytics"
  | "settings";

/** App-wide UI actions, provided once by the shell. */
export interface UiActions {
  navigate: (view: ViewId, arg?: string) => void;
  openTask: (id: string) => void;
  openCapture: (initial?: string) => void;
  openPalette: () => void;
  openShortcuts: () => void;
  openLogCall: (draft?: { start?: string; minutes?: number; people?: string[] }) => void;
  /** Add a meeting yourself (once or recurring), or edit a series you created. */
  openScheduleMeeting: (opts?: ScheduleOptions) => void;
}

export interface ScheduleOptions {
  recurring?: boolean;
  day?: string;
  series?: MeetingSeries;
}

export const UiContext = createContext<UiActions | null>(null);

export function useUi(): UiActions {
  const ctx = useContext(UiContext);
  if (!ctx) throw new Error("useUi outside provider");
  return ctx;
}
